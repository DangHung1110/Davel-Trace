"""Transactional group operations. Personal trip endpoints remain owner-scoped."""

from __future__ import annotations

import hashlib
import secrets
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select, tuple_

from BE.app.core.config import get_settings
from BE.app.core.mutations import receipt, request_fingerprint, save_receipt
from BE.app.db.models import (
    PlanningRequestModel,
    TravelerProfileModel,
    TripModel,
    utc_now,
)
from BE.app.db.session import session_scope
from BE.app.modules.catalog.application import resolve_place
from BE.app.modules.catalog.domain import CatalogUnavailable
from BE.app.modules.catalog.infrastructure import load_catalog
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.trips.infrastructure import owned_trip

from .models import (
    GroupExpenseChangeModel,
    GroupExpenseModel,
    GroupInviteModel,
    GroupMemberModel,
    GroupMessageModel,
    GroupPlanVoteModel,
    GroupSuggestionModel,
    GroupSuggestionVoteModel,
    TripGroupModel,
)

INVITE_LIFETIME = timedelta(days=3)
MAX_PARTICIPANTS = 20


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _iso(value: datetime) -> str:
    return _as_utc(value).isoformat()


def _missing() -> IdentityError:
    return IdentityError("NOT_FOUND", "Không tìm thấy chuyến nhóm.", 404)


def _invalid(message: str) -> IdentityError:
    return IdentityError("VALIDATION_ERROR", message, 422)


def _require_writable(trip: TripModel) -> None:
    if trip.lifecycle_state != "available":
        raise IdentityError("TRIP_ARCHIVED", "Hãy mở lại chuyến đi để chỉnh sửa.", 409)


def group_exists(session, trip_id: UUID) -> bool:
    return session.get(TripGroupModel, trip_id) is not None


def _trip(session, trip_id: UUID, *, lock: bool = False) -> TripModel:
    statement = select(TripModel).where(
        TripModel.trip_id == trip_id,
        TripModel.lifecycle_state.notin_(("deleted", "purged")),
    )
    if lock:
        statement = statement.with_for_update()
    trip = session.scalar(statement)
    if trip is None or not group_exists(session, trip_id):
        raise _missing()
    return trip


def _account_member(
    session, trip_id: UUID, account_id: UUID
) -> GroupMemberModel | None:
    return session.scalar(
        select(GroupMemberModel).where(
            GroupMemberModel.trip_id == trip_id,
            GroupMemberModel.account_id == account_id,
        )
    )


def _require_actor(
    session, account_id: UUID, trip: TripModel, *, leader: bool = False
) -> GroupMemberModel:
    actor = _account_member(session, trip.trip_id, account_id)
    if actor is None or not actor.active:
        raise _missing()
    if leader and trip.account_id != account_id:
        raise IdentityError(
            "GROUP_LEADER_REQUIRED", "Chỉ nhóm trưởng được thực hiện thao tác này.", 403
        )
    return actor


def require_trip_group(
    session,
    account_id: UUID,
    trip_id: UUID,
    leader: bool = False,
    *,
    lock: bool = False,
) -> TripModel:
    """Authorize a group member. Hold the trip row for a mutation when requested."""
    trip = _trip(session, trip_id, lock=lock)
    _require_actor(session, account_id, trip, leader=leader)
    return trip


def _members(session, trip_id: UUID) -> list[GroupMemberModel]:
    return list(
        session.scalars(
            select(GroupMemberModel)
            .where(
                GroupMemberModel.trip_id == trip_id,
            )
            .order_by(GroupMemberModel.created_at, GroupMemberModel.id)
        )
    )


def _attendee_count(session, trip_id: UUID) -> int:
    return session.scalar(
        select(func.count(GroupMemberModel.id)).where(
            GroupMemberModel.trip_id == trip_id,
            GroupMemberModel.active.is_(True),
        )
    )


def _require_capacity(session, trip_id: UUID) -> None:
    if _attendee_count(session, trip_id) >= MAX_PARTICIPANTS:
        raise _invalid("Chuyến đã đủ số thành viên.")


def _suggestions(session, trip_id: UUID) -> list[GroupSuggestionModel]:
    return list(
        session.scalars(
            select(GroupSuggestionModel)
            .join(
                GroupMemberModel,
                GroupMemberModel.id == GroupSuggestionModel.member_id,
            )
            .where(
                GroupSuggestionModel.trip_id == trip_id,
                GroupMemberModel.active.is_(True),
            )
            .order_by(GroupSuggestionModel.created_at, GroupSuggestionModel.id)
        )
    )


def _votes(session, trip_id: UUID) -> dict[UUID, set[UUID]]:
    grouped = defaultdict(set)
    for suggestion_id, member_id in session.execute(
        select(
            GroupSuggestionVoteModel.suggestion_id, GroupSuggestionVoteModel.member_id
        )
        .join(
            GroupSuggestionModel,
            GroupSuggestionModel.id == GroupSuggestionVoteModel.suggestion_id,
        )
        .join(
            GroupMemberModel, GroupMemberModel.id == GroupSuggestionVoteModel.member_id
        )
        .where(
            GroupSuggestionModel.trip_id == trip_id, GroupMemberModel.active.is_(True)
        )
    ):
        grouped[suggestion_id].add(member_id)
    return grouped


def group_planning_inputs(session, trip_id: UUID) -> dict:
    """Merge confirmed constraints and optional preferences without sending profiles to AI."""
    by_attendee: dict[UUID, set[str]] = defaultdict(set)
    first_choice: dict[UUID, str] = {}
    supporters: dict[str, set[UUID]] = defaultdict(set)
    accepted: dict[str, set[str]] = defaultdict(set)
    interests, foods, paces, fitness = set(), set(), [], []
    votes = _votes(session, trip_id)
    for item in _suggestions(session, trip_id):
        if item.kind == "place" and item.poi_id:
            supporters[item.poi_id].update({item.member_id, *votes.get(item.id, ())})
            by_attendee[item.member_id].add(item.poi_id)
            for voter in votes.get(item.id, ()):
                by_attendee[voter].add(item.poi_id)
            if item.priority:
                first_choice[item.member_id] = item.poi_id
            if item.approved:
                accepted["must_visit"].add(item.poi_id)
        elif item.kind == "avoid" and item.approved and item.poi_id:
            accepted["avoid"].add(item.poi_id)
        elif item.kind == "accessibility" and item.approved:
            accepted["accessibility"].add(item.title)
        elif item.kind == "food":
            foods.add(item.title)
        elif item.kind == "interest":
            interests.add(item.title)
        elif item.kind == "profile":
            interests.update(item.preference_data.get("preferred_activities", []))
            foods.update(item.preference_data.get("food_preferences", []))
            if pace := item.preference_data.get("pace"):
                paces.append(pace)
            if level := item.preference_data.get("fitness"):
                fitness.append(level)
    return {
        "priority_poi_ids": sorted(
            supporters, key=lambda key: (-len(supporters[key]), key)
        ),
        "priority_by_attendee": sorted(
            [first_choice[member]] if member in first_choice else sorted(places)
            for member, places in by_attendee.items() if places
        ),
        "support_counts": {
            identifier: len(accounts) for identifier, accounts in supporters.items()
        },
        "must_visit": sorted(accepted["must_visit"]),
        "avoid": sorted(accepted["avoid"]),
        "accessibility": sorted(accepted["accessibility"]),
        "food_preferences": sorted(foods),
        "activities": sorted(interests),
        "outdoor_bias": None,
        "pace": min(paces, default=None),
        "fitness": min(fitness, default=None),
        "attendee_count": _attendee_count(session, trip_id),
    }


def post_plan_event(session, trip_id: UUID, text: str, event_key: str) -> None:
    if not group_exists(session, trip_id):
        return
    existing = session.scalar(
        select(GroupMessageModel.id).where(
            GroupMessageModel.trip_id == trip_id,
            GroupMessageModel.event_key == event_key,
        )
    )
    if existing is None:
        session.add(
            GroupMessageModel(
                trip_id=trip_id, text=text, kind="system", event_key=event_key
            )
        )


def _costs(session, trip_id: UUID) -> list[GroupExpenseModel]:
    return list(
        session.scalars(
            select(GroupExpenseModel)
            .where(
                GroupExpenseModel.trip_id == trip_id,
                GroupExpenseModel.deleted_at.is_(None),
            )
            .order_by(GroupExpenseModel.created_at.desc(), GroupExpenseModel.id.desc())
        )
    )


def _balance(expenses: list[GroupExpenseModel]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for row in expenses:
        result[str(row.payer_id)] += row.amount_vnd
        for member_id, share in row.split.items():
            result[member_id] -= share
    return dict(result)


def group_actual_spend(session, trip_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.coalesce(func.sum(GroupExpenseModel.amount_vnd), 0)).where(
                GroupExpenseModel.trip_id == trip_id,
                GroupExpenseModel.kind == "expense",
                GroupExpenseModel.deleted_at.is_(None),
            )
        )
    )


def _expense_public(row: GroupExpenseModel) -> dict:
    return {
        "id": str(row.id),
        "author_id": str(row.author_id),
        "payer_id": str(row.payer_id),
        "member_ids": list(row.split),
        "kind": row.kind,
        "label": row.label,
        "amount_vnd": row.amount_vnd,
        "split": row.split,
        "version": row.version,
        "created_at": _iso(row.created_at),
    }


def _message_public(
    row: GroupMessageModel,
    author: GroupMemberModel | None,
    reply: GroupMessageModel | None = None,
) -> dict:
    return {
        "id": str(row.id),
        "member_id": str(row.member_id) if row.member_id else None,
        "display_name": author.display_name if author else None,
        "text": row.text,
        "poi_id": row.poi_id,
        "place_name": row.place_name,
        "kind": row.kind,
        "created_at": _iso(row.created_at),
        "reply": {
            "id": str(reply.id),
            "text": (reply.text or reply.place_name or "")[:160],
        } if reply else None,
    }


def _role(trip: TripModel, member: GroupMemberModel) -> str:
    if member.account_id == trip.account_id:
        return "leader"
    return "guest" if member.is_guest else "member"


def _summary(trip: TripModel, member: GroupMemberModel, attendee_count: int) -> dict:
    return {
        "trip_id": str(trip.trip_id),
        "title": trip.title,
        "start_date": trip.start_date.isoformat(),
        "end_date": trip.end_date.isoformat(),
        "traveler_count": trip.traveler_count,
        "attendee_count": attendee_count,
        "role": _role(trip, member),
        "read_only": trip.lifecycle_state != "available",
    }


def _detail(session, trip: TripModel, actor: GroupMemberModel) -> dict:
    members = _members(session, trip.trip_id)
    suggestions = _suggestions(session, trip.trip_id)
    votes = _votes(session, trip.trip_id)
    expenses = _costs(session, trip.trip_id)
    group = session.get(TripGroupModel, trip.trip_id)
    pinned = (
        session.get(GroupMessageModel, group.pinned_message_id)
        if group and group.pinned_message_id else None
    )
    supporters: dict[str, set[UUID]] = defaultdict(set)
    for item in suggestions:
        if item.kind == "place" and item.poi_id:
            supporters[item.poi_id].update({item.member_id, *votes.get(item.id, ())})
    return {
        **_summary(trip, actor, sum(member.active for member in members)),
        "member_id": str(actor.id),
        "pinned_meeting": _message_public(pinned, None)
        if pinned is not None and pinned.trip_id == trip.trip_id else None,
        "budget_vnd": int(trip.indicative_budget)
        if trip.indicative_budget is not None
        else None,
        "members": [
            {
                "id": str(member.id),
                "display_name": member.display_name,
                "role": _role(trip, member),
                "active": member.active,
                "is_guest": member.is_guest,
            }
            for member in members
        ],
        "suggestions": [
            {
                "id": str(item.id),
                "member_id": str(item.member_id),
                "poi_id": item.poi_id,
                "kind": item.kind,
                "title": item.title,
                "notes": item.notes,
                "priority": item.priority,
                "approved": item.approved,
                "votes": len(votes.get(item.id, ())),
                "voted": actor.id in votes.get(item.id, ()),
                "support_count": len(supporters[item.poi_id])
                if item.kind == "place" and item.poi_id
                else 0,
            }
            for item in suggestions
        ],
        "expenses": [_expense_public(row) for row in expenses],
        "spent_vnd": sum(row.amount_vnd for row in expenses if row.kind == "expense"),
        "balance": _balance(expenses),
    }


def _catalog_place(poi_id: str) -> dict:
    try:
        place = resolve_place(load_catalog(), poi_id)
    except CatalogUnavailable as error:
        raise IdentityError(
            "CATALOG_UNAVAILABLE", "Chưa tải được địa điểm. Hãy thử lại.", 503
        ) from error
    if place is None:
        raise _invalid("Địa điểm không còn trong danh sách. Hãy chọn lại.")
    return place


def _display_name(session, account_id: UUID, requested: str | None) -> str:
    if requested:
        return requested
    profile = session.get(TravelerProfileModel, account_id)
    return profile.display_name if profile else "Bạn đồng hành"


def _invite_status(row: GroupInviteModel, now: datetime) -> str:
    if row.revoked_at is not None:
        return "revoked"
    if row.used_at is not None:
        return "used"
    return "active" if _as_utc(row.expires_at) > now else "expired"


class TripGroupService:
    def __init__(self, database_url: str | None = None):
        self.database_url = (
            database_url if database_url is not None else get_settings().database_url
        )

    def list(self, account_id: UUID) -> dict:
        with session_scope(self.database_url) as session:
            attendees = select(
                GroupMemberModel.trip_id,
                func.count(GroupMemberModel.id).label("count"),
            ).where(GroupMemberModel.active.is_(True)).group_by(GroupMemberModel.trip_id).subquery()
            rows = session.execute(
                select(TripModel, GroupMemberModel, attendees.c.count)
                .join(
                    GroupMemberModel,
                    GroupMemberModel.trip_id == TripModel.trip_id,
                )
                .join(attendees, attendees.c.trip_id == TripModel.trip_id)
                .where(
                    GroupMemberModel.account_id == account_id,
                    GroupMemberModel.active.is_(True),
                    TripModel.lifecycle_state.notin_(("deleted", "purged")),
                )
                .order_by(TripModel.start_date.desc(), TripModel.trip_id)
            )
            return {"items": [_summary(trip, member, count) for trip, member, count in rows]}

    def enable(self, account_id: UUID, trip_id: UUID) -> dict:
        with session_scope(self.database_url) as session:
            trip = owned_trip(session, account_id, trip_id, lock=True)
            _require_writable(trip)
            if not group_exists(session, trip_id):
                session.add(TripGroupModel(trip_id=trip_id))
                session.flush()
                session.add(
                    GroupMemberModel(
                        trip_id=trip_id,
                        account_id=account_id,
                        display_name=_display_name(session, account_id, None),
                    )
                )
                session.flush()
            return _detail(
                session, trip, _require_actor(session, account_id, trip, leader=True)
            )

    def detail(self, account_id: UUID, trip_id: UUID) -> dict:
        with session_scope(self.database_url) as session:
            trip = _trip(session, trip_id)
            return _detail(session, trip, _require_actor(session, account_id, trip))

    def create_invite(self, account_id: UUID, trip_id: UUID) -> dict:
        with session_scope(self.database_url) as session:
            trip = require_trip_group(
                session, account_id, trip_id, leader=True, lock=True
            )
            _require_writable(trip)
            _require_capacity(session, trip_id)
            code = secrets.token_urlsafe(16)
            invite = GroupInviteModel(
                trip_id=trip_id,
                code_hash=hashlib.sha256(code.encode()).hexdigest(),
                expires_at=utc_now() + INVITE_LIFETIME,
            )
            session.add(invite)
            session.flush()
            return {
                "id": str(invite.id),
                "code": code,
                "expires_at": _iso(invite.expires_at),
            }

    def invites(self, account_id: UUID, trip_id: UUID) -> dict:
        with session_scope(self.database_url) as session:
            require_trip_group(session, account_id, trip_id, leader=True)
            rows = session.scalars(
                select(GroupInviteModel)
                .where(
                    GroupInviteModel.trip_id == trip_id,
                )
                .order_by(GroupInviteModel.created_at.desc())
                .limit(100)
            )
            now = utc_now()
            return {
                "items": [
                    {
                        "id": str(row.id),
                        "expires_at": _iso(row.expires_at),
                        "status": _invite_status(row, now),
                    }
                    for row in rows
                ]
            }

    def revoke_invite(self, account_id: UUID, trip_id: UUID, invite_id: UUID) -> dict:
        with session_scope(self.database_url) as session:
            trip = require_trip_group(
                session, account_id, trip_id, leader=True, lock=True
            )
            invite = session.get(GroupInviteModel, invite_id)
            if invite is None or invite.trip_id != trip_id:
                raise _missing()
            if _invite_status(invite, utc_now()) == "active":
                invite.revoked_at = utc_now()
            return _detail(session, trip, _require_actor(session, account_id, trip))

    def join(self, account_id: UUID, code: str, name: str | None) -> dict:
        with session_scope(self.database_url) as session:
            fingerprint = hashlib.sha256(code.encode()).hexdigest()
            fields = session.execute(
                select(GroupInviteModel.id, GroupInviteModel.trip_id).where(
                    GroupInviteModel.code_hash == fingerprint,
                )
            ).one_or_none()
            if fields is None:
                raise _invalid("Mã lời mời không hợp lệ hoặc đã hết hạn.")
            trip = _trip(session, fields.trip_id, lock=True)
            _require_writable(trip)
            invite = session.get(GroupInviteModel, fields.id)
            member = _account_member(session, trip.trip_id, account_id)
            if member is not None and member.active:
                return _detail(session, trip, member)
            if invite is None or _invite_status(invite, utc_now()) != "active":
                raise _invalid("Mã lời mời không hợp lệ hoặc đã hết hạn.")
            _require_capacity(session, trip.trip_id)
            if member is None:
                member = GroupMemberModel(trip_id=trip.trip_id, account_id=account_id)
                session.add(member)
            member.active = True
            member.display_name = _display_name(session, account_id, name)
            invite.used_at = utc_now()
            session.flush()
            return _detail(session, trip, member)

    def add_guest(self, account_id: UUID, trip_id: UUID, name: str) -> dict:
        with session_scope(self.database_url) as session:
            trip = require_trip_group(
                session, account_id, trip_id, leader=True, lock=True
            )
            _require_writable(trip)
            _require_capacity(session, trip_id)
            session.add(
                GroupMemberModel(trip_id=trip_id, display_name=name, is_guest=True)
            )
            session.flush()
            return _detail(session, trip, _require_actor(session, account_id, trip))

    def remove_member(self, account_id: UUID, trip_id: UUID, member_id: UUID) -> None:
        with session_scope(self.database_url) as session:
            trip = _trip(session, trip_id, lock=True)
            actor = _require_actor(session, account_id, trip)
            member = session.get(GroupMemberModel, member_id)
            if member is None or member.trip_id != trip_id or not member.active:
                raise _missing()
            if member.account_id == trip.account_id:
                raise _invalid("Nhóm trưởng cần giữ quyền quản lý chuyến đi.")
            if actor.id != member_id and trip.account_id != account_id:
                raise IdentityError(
                    "GROUP_LEADER_REQUIRED",
                    "Chỉ nhóm trưởng được quản lý thành viên.",
                    403,
                )
            member.active = False
            session.execute(
                delete(GroupSuggestionVoteModel).where(
                    GroupSuggestionVoteModel.member_id == member_id
                )
            )
            if member.account_id is not None:
                requests = select(PlanningRequestModel.request_id).where(
                    PlanningRequestModel.trip_id == trip_id
                )
                session.execute(
                    delete(GroupPlanVoteModel).where(
                        GroupPlanVoteModel.voter_account_id == member.account_id,
                        GroupPlanVoteModel.request_id.in_(requests),
                    )
                )

    def _contributor(self, session, trip, actor, member_id):
        if member_id is None or member_id == actor.id:
            return actor
        member = session.get(GroupMemberModel, member_id)
        if member is None or member.trip_id != trip.trip_id or not member.active:
            raise _missing()
        if trip.account_id != actor.account_id or not member.is_guest:
            raise IdentityError(
                "GROUP_INPUT_FORBIDDEN", "Bạn chỉ có thể gửi góp ý của mình.", 403
            )
        return member

    def suggest(self, account_id: UUID, trip_id: UUID, values: dict) -> dict:
        return self.suggest_many(account_id, trip_id, [values])

    def suggest_many(self, account_id: UUID, trip_id: UUID, items: list[dict]) -> dict:
        with session_scope(self.database_url) as session:
            trip = _trip(session, trip_id, lock=True)
            actor = _require_actor(session, account_id, trip)
            _require_writable(trip)
            for values in items:
                self._save_suggestion(session, trip, actor, values)
            return _detail(session, trip, actor)

    def _save_suggestion(self, session, trip, actor, values):
        contributor = self._contributor(
            session, trip, actor, values.get("member_id")
        )
        poi_id, kind = values.get("poi_id"), values["kind"]
        title, notes = values["title"], values["notes"]
        preference_data = {}
        if values["use_profile"]:
            if contributor.id != actor.id:
                raise _invalid("Mỗi người tự chọn dùng sở thích từ hồ sơ của mình.")
            profile = session.get(TravelerProfileModel, actor.account_id)
            if profile is None:
                raise _invalid("Hãy tạo hồ sơ trước khi dùng lại sở thích.")
            kind, poi_id = "profile", None
            title, notes = "Sở thích từ hồ sơ", ""
            preference_data = {
                "preferred_activities": profile.preferred_activities,
                "food_preferences": profile.food_preferences,
                "pace": profile.pace,
                "fitness": profile.fitness,
            }
        elif poi_id is not None:
            if kind not in {"place", "avoid"}:
                raise _invalid(
                    "Chỉ đính kèm địa điểm cho điểm muốn ghé hoặc muốn tránh."
                )
            title = _catalog_place(poi_id)["name"]
        if not title:
            raise _invalid("Hãy nhập nội dung góp ý.")
        priority = bool(values["priority"] and kind == "place" and poi_id)
        existing = session.scalars(
            select(GroupSuggestionModel).where(
                GroupSuggestionModel.member_id == contributor.id,
                GroupSuggestionModel.kind == kind,
            )
        ).all()
        row = next(
            (
                item
                for item in existing
                if (
                    kind == "profile"
                    or (poi_id and item.poi_id == poi_id)
                    or (
                        poi_id is None
                        and item.poi_id is None
                        and item.title.casefold() == title.casefold()
                    )
                )
            ),
            None,
        )
        if priority:
            for item in existing:
                if item is not row:
                    item.priority = False
        if row is None:
            row = GroupSuggestionModel(
                trip_id=trip.trip_id,
                member_id=contributor.id,
                poi_id=poi_id,
                kind=kind,
                title=title,
            )
            session.add(row)
        row.notes, row.priority, row.preference_data = (
            notes,
            priority,
            preference_data,
        )
        session.flush()

    def suggestion_action(
        self,
        account_id: UUID,
        trip_id: UUID,
        suggestion_id: UUID,
        action: str,
        enabled: bool = False,
    ) -> dict:
        with session_scope(self.database_url) as session:
            trip = _trip(session, trip_id, lock=True)
            actor = _require_actor(
                session, account_id, trip, leader=(action == "approval")
            )
            _require_writable(trip)
            row = session.get(GroupSuggestionModel, suggestion_id)
            if row is None or row.trip_id != trip_id:
                raise _missing()
            contributor = session.get(GroupMemberModel, row.member_id)
            if contributor is None or not contributor.active:
                raise _missing()
            if action == "delete":
                self._contributor(session, trip, actor, row.member_id)
                if row.approved and trip.account_id != account_id:
                    raise _invalid("Nhờ nhóm trưởng bỏ xác nhận trước khi xóa góp ý.")
                session.delete(row)
            elif action == "approval":
                if row.kind not in {"accessibility", "place", "avoid"}:
                    raise _invalid("Chỉ xác nhận yêu cầu hỗ trợ hoặc địa điểm cụ thể.")
                if row.kind != "accessibility" and not row.poi_id:
                    raise _invalid(
                        "Hãy chọn địa điểm trong danh sách trước khi xác nhận."
                    )
                conflicts = [
                    item
                    for item in _suggestions(session, trip_id)
                    if (
                        item.approved
                        and item.poi_id == row.poi_id
                        and {item.kind, row.kind} == {"place", "avoid"}
                    )
                ]
                if enabled and conflicts:
                    raise _invalid("Địa điểm đã được xác nhận ở danh sách ngược lại.")
                row.approved = enabled
            else:
                if row.kind != "place":
                    raise _invalid("Chỉ bình chọn điểm muốn ghé.")
                vote = session.get(GroupSuggestionVoteModel, (row.id, actor.id))
                if enabled and vote is None:
                    session.add(
                        GroupSuggestionVoteModel(
                            suggestion_id=row.id, member_id=actor.id
                        )
                    )
                if not enabled and vote is not None:
                    session.delete(vote)
            session.flush()
            return _detail(session, trip, actor)

    def chat(
        self, account_id: UUID, trip_id: UUID, before: UUID | None, limit: int
    ) -> dict:
        with session_scope(self.database_url) as session:
            require_trip_group(session, account_id, trip_id)
            statement = (
                select(GroupMessageModel, GroupMemberModel)
                .outerjoin(
                    GroupMemberModel,
                    GroupMemberModel.id == GroupMessageModel.member_id,
                )
                .where(GroupMessageModel.trip_id == trip_id)
            )
            if before is not None:
                cursor = session.get(GroupMessageModel, before)
                if cursor is None or cursor.trip_id != trip_id:
                    raise _missing()
                statement = statement.where(
                    tuple_(GroupMessageModel.created_at, GroupMessageModel.id)
                    < (cursor.created_at, cursor.id),
                )
            rows = session.execute(
                statement.order_by(
                    GroupMessageModel.created_at.desc(),
                    GroupMessageModel.id.desc(),
                ).limit(limit + 1)
            ).all()
            reply_ids = {row.reply_to_id for row, _ in rows if row.reply_to_id}
            replies = {
                row.id: row for row in session.scalars(
                    select(GroupMessageModel).where(
                        GroupMessageModel.trip_id == trip_id,
                        GroupMessageModel.id.in_(reply_ids),
                    )
                )
            } if reply_ids else {}
            return {
                "items": [
                    _message_public(row, author, replies.get(row.reply_to_id))
                    for row, author in reversed(rows[:limit])
                ],
                "has_more": len(rows) > limit,
            }

    def post_message(
        self, account_id: UUID, trip_id: UUID, text: str, poi_id: str | None,
        reply_to_id: UUID | None = None,
    ) -> dict:
        with session_scope(self.database_url) as session:
            trip = _trip(session, trip_id, lock=True)
            actor = _require_actor(session, account_id, trip)
            _require_writable(trip)
            place_name = _catalog_place(poi_id)["name"] if poi_id else None
            reply = session.get(GroupMessageModel, reply_to_id) if reply_to_id else None
            if reply_to_id and (reply is None or reply.trip_id != trip_id or reply.kind == "system"):
                raise _missing()
            if not text and not place_name:
                raise _invalid("Hãy nhập tin nhắn hoặc chọn điểm hẹn.")
            row = GroupMessageModel(
                trip_id=trip_id,
                member_id=actor.id,
                text=text,
                poi_id=poi_id,
                place_name=place_name,
                reply_to_id=reply_to_id,
                kind="meeting" if poi_id else "message",
            )
            session.add(row)
            session.flush()
            return _message_public(row, actor, reply)

    def pin_meeting(
        self, account_id: UUID, trip_id: UUID, message_id: UUID | None
    ) -> dict:
        with session_scope(self.database_url) as session:
            trip = require_trip_group(session, account_id, trip_id, leader=True, lock=True)
            _require_writable(trip)
            group = session.get(TripGroupModel, trip_id)
            message = session.get(GroupMessageModel, message_id) if message_id else None
            if message_id and (message is None or message.trip_id != trip_id or message.kind != "meeting"):
                raise _missing()
            group.pinned_message_id = message_id
            return {"pinned_meeting": _message_public(message, None) if message else None}

    def save_expense(
        self,
        account_id: UUID,
        trip_id: UUID,
        values: dict,
        expense_id: UUID | None = None,
        *,
        key: str | None = None,
    ) -> dict:
        with session_scope(self.database_url) as session:
            trip = _trip(session, trip_id, lock=True)
            actor = _require_actor(session, account_id, trip)
            _require_writable(trip)
            if key is not None:
                fingerprint = request_fingerprint(values)
                prior, key_hash = receipt(
                    session,
                    account_id,
                    "create_group_expense",
                    str(trip_id),
                    key,
                    fingerprint,
                )
                if prior:
                    return _detail(session, trip, actor)
            row = (
                self._editable_expense(session, trip, actor, expense_id)
                if expense_id
                else None
            )
            kind = values["kind"]
            before = _expense_public(row) if row else None
            if row and values.get("version") not in (None, row.version):
                raise IdentityError(
                    "VERSION_CONFLICT", "Khoản chi đã thay đổi. Hãy tải lại.", 409
                )
            if row and row.kind != kind:
                raise _invalid("Không thể đổi loại khoản đã ghi.")
            payer_id, recipients = values["payer_id"], values["member_ids"]
            if len(set(recipients)) != len(recipients):
                raise _invalid("Mỗi người chỉ được chọn một lần.")
            active = {
                member.id for member in _members(session, trip_id) if member.active
            }
            # A saved entry may retain its historical participants after someone leaves.
            historical = (
                {UUID(key) for key in row.split} | {row.payer_id} if row else set()
            )
            amount = values["amount_vnd"]
            if kind == "settlement":
                if len(recipients) != 1 or payer_id == recipients[0]:
                    raise _invalid("Chọn một người nhận khác người chuyển tiền.")
                if (
                    actor.id not in {payer_id, recipients[0]}
                    and trip.account_id != account_id
                ):
                    raise IdentityError(
                        "GROUP_PAYMENT_FORBIDDEN",
                        "Bạn chỉ có thể ghi lần hoàn tiền của mình.",
                        403,
                    )
                balance = _balance(
                    [item for item in _costs(session, trip_id) if item is not row]
                )
                maximum = min(
                    -balance.get(str(payer_id), 0), balance.get(str(recipients[0]), 0)
                )
                if amount > maximum:
                    raise _invalid("Số tiền hoàn vượt số tiền còn cần trả hoặc nhận.")
                split = {str(recipients[0]): amount}
            else:
                if not {payer_id, *recipients}.issubset(active | historical):
                    raise _invalid("Chỉ chọn thành viên của chuyến đi.")
                base, remainder = divmod(amount, len(recipients))
                split = {
                    str(identifier): base + (index < remainder)
                    for index, identifier in enumerate(sorted(recipients))
                }
            if row is None:
                row = GroupExpenseModel(trip_id=trip_id, author_id=actor.id, kind=kind)
                session.add(row)
            else:
                row.version += 1
            row.payer_id, row.label, row.amount_vnd, row.split = (
                payer_id,
                values["label"],
                amount,
                split,
            )
            session.flush()
            session.add(
                GroupExpenseChangeModel(
                    expense_id=row.id,
                    actor_id=actor.id,
                    action="create" if before is None else "update",
                    before=before,
                    after=_expense_public(row),
                )
            )
            if key is not None:
                save_receipt(
                    session,
                    account_id,
                    "create_group_expense",
                    str(trip_id),
                    key_hash,
                    fingerprint,
                    row.id,
                    201,
                )
            return _detail(session, trip, actor)

    @staticmethod
    def _editable_expense(session, trip, actor, expense_id):
        row = session.get(GroupExpenseModel, expense_id)
        if row is None or row.trip_id != trip.trip_id or row.deleted_at is not None:
            raise _missing()
        if row.author_id != actor.id:
            raise IdentityError(
                "GROUP_EXPENSE_FORBIDDEN",
                "Chỉ người ghi khoản chi được chỉnh sửa.",
                403,
            )
        return row

    def delete_expense(self, account_id: UUID, trip_id: UUID, expense_id: UUID) -> dict:
        with session_scope(self.database_url) as session:
            trip = _trip(session, trip_id, lock=True)
            actor = _require_actor(session, account_id, trip)
            _require_writable(trip)
            row = self._editable_expense(session, trip, actor, expense_id)
            session.add(
                GroupExpenseChangeModel(
                    expense_id=row.id,
                    actor_id=actor.id,
                    action="delete",
                    before=_expense_public(row),
                )
            )
            row.deleted_at = utc_now()
            session.flush()
            return _detail(session, trip, actor)

    def expense_history(
        self, account_id: UUID, trip_id: UUID, expense_id: UUID
    ) -> dict:
        with session_scope(self.database_url) as session:
            require_trip_group(session, account_id, trip_id)
            row = session.get(GroupExpenseModel, expense_id)
            if row is None or row.trip_id != trip_id:
                raise _missing()
            rows = session.scalars(
                select(GroupExpenseChangeModel)
                .where(
                    GroupExpenseChangeModel.expense_id == expense_id,
                )
                .order_by(
                    GroupExpenseChangeModel.created_at.desc(),
                    GroupExpenseChangeModel.id,
                )
            )
            return {
                "items": [
                    {
                        "action": item.action,
                        "actor_id": str(item.actor_id),
                        "before": item.before,
                        "after": item.after,
                        "created_at": _iso(item.created_at),
                    }
                    for item in rows
                ]
            }
