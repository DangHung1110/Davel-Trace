"""Transactional use cases for durable itinerary planning and version history."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Callable
from uuid import UUID, uuid4

from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from BE.app.core.config import Settings, get_settings
from BE.app.core.request_context import get_correlation_id
from BE.app.db.models import (
    AcceptanceRecordModel,
    ActiveItineraryVersionModel,
    ExpenseEntryModel,
    ItineraryAlternativeModel,
    ItineraryVersionModel,
    ItineraryVersionTransitionModel,
    PlanningRequestModel,
    TripActivityModel,
    TripDayModel,
    TripModel,
)
from BE.app.db.session import session_scope
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.planning_lifecycle.application import (
    alternative_fingerprint,
    canonical_fingerprint,
    internal_acceptance_key,
)
from BE.app.modules.planning_lifecycle.infrastructure import (
    acceptance_public,
    active_for_trip,
    owned_alternative,
    owned_request,
    owned_trip,
    owned_version,
    request_public,
    transition_public,
    version_detail,
    version_summary,
)
from BE.app.modules.trips.service import trip_public
from BE.app.routers.itinerary import ItineraryIn, itinerary as legacy_itinerary
from BE.app.schemas.trip import TripRequest


Planner = Callable[[dict, int, str], dict]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_key(value: str) -> str:
    value = str(value or "").strip()
    if not 8 <= len(value) <= 128:
        raise IdentityError(
            "VALIDATION_ERROR", "Idempotency-Key phải dài 8-128 ký tự.", 422
        )
    return value


def _legacy_payload(result) -> dict:
    if isinstance(result, JSONResponse):
        payload = json.loads(result.body.decode("utf-8"))
        code = payload.get("error")
        if isinstance(code, dict):
            code = code.get("code")
        raise IdentityError(
            str(code or "PLANNING_FAILED"),
            str(payload.get("message") or "Không thể lập lịch."),
            result.status_code,
        )
    if not isinstance(result, dict):
        raise RuntimeError("planner returned an invalid payload")
    return result


def _profile(snapshot: dict) -> dict:
    return {
        "party_type": snapshot.get("party_type", "solo"),
        "trip_purpose": snapshot.get("trip_purpose", "leisure"),
        "spending_level": {
            "economy": 1, "balanced": 2, "premium": 3
        }.get(snapshot.get("spending_style"), 2),
        "pace": snapshot.get("pace", 2),
        "fitness": snapshot.get("fitness", 2),
        "food_prefs": snapshot.get("food_preferences", []),
        "allergy": snapshot.get("allergies", []),
        "activities": snapshot.get("preferred_activities", []),
        "accessibility": snapshot.get("accessibility_needs", []),
        "must_avoid": snapshot.get("must_avoid", []),
        "transport": snapshot.get("usual_transport", []),
    }


def _trip_request(snapshot: dict, remaining: dict) -> dict:
    start = snapshot.get("day_start") or "07:00:00"
    end = snapshot.get("day_end") or "18:00:00"
    days = len(snapshot.get("days") or []) or 1
    budget = snapshot.get("indicative_budget")
    actual = float(remaining.get("actual_spend") or 0)
    raw_remaining_from = remaining.get("remaining_from")
    remaining_from = str(raw_remaining_from or start)
    if "T" in remaining_from:
        remaining_from = remaining_from.split("T", 1)[1]
    elif " " in remaining_from:
        remaining_from = remaining_from.rsplit(" ", 1)[-1]
    avoid = list(dict.fromkeys([
        *(remaining.get("unavailable_poi_ids") or []),
        *(remaining.get("completed_poi_ids") or []),
        *(remaining.get("skipped_poi_ids") or []),
    ]))
    return TripRequest(
        trip_id=snapshot["id"],
        user_id=snapshot.get("account_id", "owned-user"),
        city="da-nang",
        date=snapshot.get("start_date", ""),
        start_time=remaining_from[:5],
        end_time=str(end)[:5],
        days=max(1, min(2, days)),
        travelers=snapshot.get("traveler_count", 1),
        budget=max(0, int(float(budget or 0) - actual)),
        transport=[snapshot.get("preferred_transport") or "mixed"],
        avoid=avoid,
        profile=_profile(snapshot.get("profile_snapshot") or {}),
    ).model_dump()


class PlanningLifecycleService:
    def __init__(
        self,
        settings: Settings | None = None,
        planner: Planner | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._planner = planner or self._run_legacy_planner

    def _run_legacy_planner(self, trip_input: dict, target: int, kind: str) -> dict:
        timeout = 15 if kind == "replan" else 30
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="planner")
        future = executor.submit(
            legacy_itinerary,
            ItineraryIn(trip=TripRequest(**trip_input)),
            True,
        )
        try:
            result = future.result(timeout=timeout)
        except FutureTimeout as exc:
            future.cancel()
            raise IdentityError(
                "PLANNING_TIMEOUT" if kind == "plan" else "REPLAN_TIMEOUT",
                "Lập lịch quá thời gian cho phép, bạn có thể thử lại an toàn.",
                504,
            ) from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return _legacy_payload(result)

    def create_planning_request(
        self,
        principal,
        trip_id: UUID,
        idempotency_key: str,
        *,
        target_count: int = 5,
        constraint_overrides: dict | None = None,
        request_kind: str = "plan",
        source_version_id: UUID | None = None,
        remaining_context: dict | None = None,
    ) -> dict:
        key = _require_key(idempotency_key)
        if not 1 <= target_count <= 5:
            raise IdentityError("VALIDATION_ERROR", "Số phương án phải từ 1 đến 5.", 422)
        overrides = dict(constraint_overrides or {})
        remaining = dict(remaining_context or {})

        with session_scope(self.settings.database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id, lock=True)
            snapshot = trip_public(session, trip)
            snapshot["account_id"] = str(principal.account_id)
            effective_snapshot = dict(snapshot)
            for field in (
                "indicative_budget", "preferred_transport", "day_start",
                "day_end", "traveler_count", "preference_overrides",
            ):
                if field in overrides:
                    effective_snapshot[field] = overrides[field]
            input_payload = {
                "trip": effective_snapshot,
                "constraint_overrides": overrides,
                "request_kind": request_kind,
            }
            fingerprint = canonical_fingerprint({
                "trip_id": str(trip_id),
                "trip_version": trip.version,
                "target_count": target_count,
                "overrides": overrides,
                "source_version_id": str(source_version_id) if source_version_id else None,
                "remaining_context": remaining,
            })
            existing = session.scalar(select(PlanningRequestModel).where(
                PlanningRequestModel.account_id == principal.account_id,
                PlanningRequestModel.request_kind == request_kind,
                PlanningRequestModel.idempotency_key == key,
            ))
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise IdentityError(
                        "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key đã được dùng cho nội dung khác.",
                        409,
                    )
                return request_public(session, existing)
            row = PlanningRequestModel(
                account_id=principal.account_id,
                trip_id=trip.trip_id,
                request_kind=request_kind,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                source_version_id=source_version_id,
                trip_version=trip.version,
                data_version=self.settings.snapshot_name,
                input_payload=input_payload,
                remaining_context=remaining,
                status="running",
                target_count=target_count,
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                existing = session.scalar(select(PlanningRequestModel).where(
                    PlanningRequestModel.account_id == principal.account_id,
                    PlanningRequestModel.request_kind == request_kind,
                    PlanningRequestModel.idempotency_key == key,
                ))
                if existing is None:
                    raise
                if existing.request_fingerprint != fingerprint:
                    raise IdentityError(
                        "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key đã được dùng cho nội dung khác.",
                        409,
                    )
                return request_public(session, existing)
            request_id = row.request_id
            planner_input = _trip_request(effective_snapshot, remaining)

        try:
            planned = self._planner(planner_input, target_count, request_kind)
            plans = list(planned.get("plans") or [])[:target_count]
        except IdentityError as exc:
            with session_scope(self.settings.database_url) as session:
                row = session.get(PlanningRequestModel, request_id, with_for_update=True)
                row.status = "failed"
                row.failure_code = exc.code
                row.completed_at = _now()
                session.flush()
                return request_public(session, row)
        except Exception:
            with session_scope(self.settings.database_url) as session:
                row = session.get(PlanningRequestModel, request_id, with_for_update=True)
                row.status = "failed"
                row.failure_code = "PLANNING_FAILED"
                row.completed_at = _now()
                session.flush()
                return request_public(session, row)

        with session_scope(self.settings.database_url) as session:
            row = session.get(PlanningRequestModel, request_id, with_for_update=True)
            seen: set[str] = set()
            rank = 0
            for plan in plans:
                gate = dict(plan.get("gate") or {})
                fingerprint = alternative_fingerprint(plan)
                families = gate.get("families") or {}
                complete_gate = (
                    len(families) == 5
                    and all(bool(item.get("passed")) for item in families.values())
                )
                if (
                    not plan.get("activities")
                    or not gate.get("passed")
                    or not complete_gate
                    or fingerprint in seen
                ):
                    continue
                seen.add(fingerprint)
                rank += 1
                public_plan = dict(plan)
                public_plan["preserved_completed"] = remaining.get(
                    "completed_activity_ids", []
                )
                session.add(ItineraryAlternativeModel(
                    request_id=row.request_id,
                    trip_id=row.trip_id,
                    account_id=row.account_id,
                    fingerprint=fingerprint,
                    profile=str(plan.get("profile") or "balanced"),
                    plan_payload=public_plan,
                    gate_payload=gate,
                    deterministic_rank=rank,
                    deterministic_score=plan.get("deterministic_score"),
                    data_version=row.data_version,
                ))
            row.returned_count = rank
            row.shortage_reason = None if rank >= row.target_count else str(
                (planned.get("solution_pool") or {}).get("shortage_reason")
                or "insufficient_feasible_supply"
            )
            row.status = "completed"
            row.completed_at = _now()
            session.flush()
            return request_public(session, row)

    def get_request(self, principal, request_id: UUID) -> dict:
        with session_scope(self.settings.database_url) as session:
            return request_public(
                session, owned_request(session, principal.account_id, request_id)
            )

    def accept(self, principal, alternative_id: UUID, idempotency_key: str) -> dict:
        key = _require_key(idempotency_key)
        with session_scope(self.settings.database_url) as session:
            alternative = owned_alternative(
                session, principal.account_id, alternative_id, lock=True
            )
            request = session.get(PlanningRequestModel, alternative.request_id)
            reason = "replan_accept" if request.request_kind == "replan" else "accept"
            replay = session.scalar(select(ItineraryVersionTransitionModel).where(
                ItineraryVersionTransitionModel.account_id == principal.account_id,
                ItineraryVersionTransitionModel.reason == reason,
                ItineraryVersionTransitionModel.idempotency_key == key,
            ))
            if replay is not None:
                version = session.get(ItineraryVersionModel, replay.to_version_id)
                if version.alternative_id != alternative.alternative_id:
                    raise IdentityError(
                        "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key đã chọn một phương án khác.", 409,
                    )
                acceptance = session.scalar(select(AcceptanceRecordModel).where(
                    AcceptanceRecordModel.itinerary_version_id == version.version_id
                ))
                active = active_for_trip(session, version.trip_id)
                return {
                    "acceptance": acceptance_public(acceptance),
                    "version": version_detail(version, active.version_id if active else None),
                    "transition": transition_public(replay),
                }
            trip = owned_trip(session, principal.account_id, alternative.trip_id, lock=True)
            if request.status != "completed" or alternative.selectability_state != "current":
                raise IdentityError("ALTERNATIVE_STALE", "Phương án không còn có thể chọn.", 409)
            if trip.version != request.trip_version or request.data_version != self.settings.snapshot_name:
                alternative.selectability_state = "invalidated"
                trip.review_state = "needs_review"
                raise IdentityError("ALTERNATIVE_STALE", "Dữ liệu chuyến đi đã thay đổi.", 409)
            families = alternative.gate_payload.get("families") or {}
            if (
                not alternative.gate_payload.get("passed")
                or len(families) != 5
                or not all(bool(item.get("passed")) for item in families.values())
            ):
                alternative.selectability_state = "invalidated"
                raise IdentityError("GATE_FAILED", "Phương án không còn đạt cổng khả thi.", 422)

            active = active_for_trip(session, trip.trip_id, lock=True)
            ordinal = int(session.scalar(select(func.count()).select_from(
                ItineraryVersionModel
            ).where(ItineraryVersionModel.trip_id == trip.trip_id)) or 0) + 1
            version = ItineraryVersionModel(
                version_id=uuid4(),
                account_id=principal.account_id,
                trip_id=trip.trip_id,
                alternative_id=alternative.alternative_id,
                parent_version_id=request.source_version_id,
                ordinal=ordinal,
                plan_payload=alternative.plan_payload,
                gate_payload=alternative.gate_payload,
                request_payload=request.input_payload,
                data_version=alternative.data_version,
                deterministic_rank=alternative.deterministic_rank,
                deterministic_score=alternative.deterministic_score,
            )
            session.add(version)
            session.flush()
            parent_acceptance = None
            if request.source_version_id:
                parent_acceptance = session.scalar(select(AcceptanceRecordModel).where(
                    AcceptanceRecordModel.itinerary_version_id == request.source_version_id
                ))
            acceptance = AcceptanceRecordModel(
                idempotency_key=internal_acceptance_key(
                    str(principal.account_id), reason, key
                ),
                itinerary_id=str(alternative.alternative_id),
                trip_id=str(trip.trip_id),
                parent_acceptance_id=(
                    parent_acceptance.acceptance_id if parent_acceptance else None
                ),
                data_version=alternative.data_version,
                request_payload=request.input_payload,
                plan_payload=alternative.plan_payload,
                gate_payload=alternative.gate_payload,
                deterministic_rank=alternative.deterministic_rank,
                deterministic_score=alternative.deterministic_score,
                account_id=principal.account_id,
                request_id=request.request_id,
                alternative_id=alternative.alternative_id,
                itinerary_version_id=version.version_id,
            )
            session.add(acceptance)
            transition = ItineraryVersionTransitionModel(
                account_id=principal.account_id,
                trip_id=trip.trip_id,
                from_version_id=active.version_id if active else None,
                to_version_id=version.version_id,
                reason=reason,
                idempotency_key=key,
                correlation_id=get_correlation_id(),
            )
            session.add(transition)
            if active is None:
                active = ActiveItineraryVersionModel(
                    trip_id=trip.trip_id,
                    account_id=principal.account_id,
                    version_id=version.version_id,
                )
                session.add(active)
            else:
                active.version_id = version.version_id
                active.revision += 1
                active.updated_at = _now()
            alternative.selectability_state = "selected"
            session.execute(update(ItineraryAlternativeModel).where(
                ItineraryAlternativeModel.request_id == request.request_id,
                ItineraryAlternativeModel.alternative_id != alternative.alternative_id,
                ItineraryAlternativeModel.selectability_state == "current",
            ).values(selectability_state="superseded"))
            trip.review_state = "current"
            session.flush()
            return {
                "acceptance": acceptance_public(acceptance),
                "version": version_detail(version, version.version_id),
                "transition": transition_public(transition),
            }

    def list_versions(self, principal, trip_id: UUID, limit=50, offset=0) -> dict:
        with session_scope(self.settings.database_url) as session:
            owned_trip(session, principal.account_id, trip_id)
            active = active_for_trip(session, trip_id)
            rows = list(session.scalars(select(ItineraryVersionModel).where(
                ItineraryVersionModel.trip_id == trip_id,
                ItineraryVersionModel.account_id == principal.account_id,
            ).order_by(
                ItineraryVersionModel.created_at.desc(),
                ItineraryVersionModel.ordinal.desc(),
            ).offset(max(0, offset)).limit(max(1, min(100, limit)))))
            items = []
            for row in rows:
                item = version_summary(row, active.version_id if active else None)
                transition = session.scalar(select(ItineraryVersionTransitionModel).where(
                    ItineraryVersionTransitionModel.to_version_id == row.version_id
                ).order_by(ItineraryVersionTransitionModel.occurred_at.desc()))
                item["reason"] = transition.reason if transition else "accept"
                items.append(item)
            return {"items": items, "active_version_id": str(active.version_id) if active else None}

    def get_version(self, principal, version_id: UUID) -> dict:
        with session_scope(self.settings.database_url) as session:
            row = owned_version(session, principal.account_id, version_id)
            active = active_for_trip(session, row.trip_id)
            result = version_detail(row, active.version_id if active else None)
            acceptance = session.scalar(select(AcceptanceRecordModel).where(
                AcceptanceRecordModel.itinerary_version_id == row.version_id
            ))
            result["acceptance"] = acceptance_public(acceptance) if acceptance else None
            return result

    def activate(self, principal, version_id: UUID, idempotency_key: str) -> dict:
        key = _require_key(idempotency_key)
        with session_scope(self.settings.database_url) as session:
            version = owned_version(session, principal.account_id, version_id)
            trip = owned_trip(session, principal.account_id, version.trip_id, lock=True)
            replay = session.scalar(select(ItineraryVersionTransitionModel).where(
                ItineraryVersionTransitionModel.account_id == principal.account_id,
                ItineraryVersionTransitionModel.reason == "reactivate",
                ItineraryVersionTransitionModel.idempotency_key == key,
            ))
            if replay:
                if replay.to_version_id != version.version_id:
                    raise IdentityError("IDEMPOTENCY_CONFLICT", "Khóa đã kích hoạt phiên bản khác.", 409)
                current = active_for_trip(session, trip.trip_id)
                return {
                    "version": version_detail(
                        version, current.version_id if current else None
                    ),
                    "transition": transition_public(replay),
                }
            active = active_for_trip(session, trip.trip_id, lock=True)
            if active is None:
                raise IdentityError("STATE_CONFLICT", "Chuyến đi chưa có lịch đang dùng.", 409)
            transition = ItineraryVersionTransitionModel(
                account_id=principal.account_id,
                trip_id=trip.trip_id,
                from_version_id=active.version_id,
                to_version_id=version.version_id,
                reason="reactivate",
                idempotency_key=key,
                correlation_id=get_correlation_id(),
            )
            session.add(transition)
            active.version_id = version.version_id
            active.revision += 1
            active.updated_at = _now()
            trip.review_state = "current"
            session.flush()
            return {"version": version_detail(version, version.version_id),
                    "transition": transition_public(transition)}

    def replan(
        self,
        principal,
        trip_id: UUID,
        idempotency_key: str,
        payload: dict,
    ) -> dict:
        source_id = UUID(str(payload.get("source_version_id")))
        with session_scope(self.settings.database_url) as session:
            source = owned_version(session, principal.account_id, source_id)
            if source.trip_id != trip_id:
                raise IdentityError("NOT_FOUND", "Không tìm thấy phiên bản lịch trình.", 404)
            active = active_for_trip(session, trip_id)
            if active is None or active.version_id != source.version_id:
                raise IdentityError("SOURCE_VERSION_STALE", "Phiên bản nguồn không còn đang dùng.", 409)
            activity_rows = list(session.execute(
                select(
                    TripActivityModel.activity_id,
                    TripActivityModel.progress_state,
                    TripActivityModel.poi_id,
                )
                .join(TripDayModel, TripDayModel.day_id == TripActivityModel.day_id)
                .where(TripDayModel.trip_id == trip_id)
            ))
            known = {
                str(item.activity_id): {
                    "state": item.progress_state,
                    "poi_id": item.poi_id,
                }
                for item in activity_rows
            }
            completed = list(dict.fromkeys(payload.get("completed_activity_ids") or [
                key for key, item in known.items() if item["state"] == "completed"
            ]))
            skipped = list(dict.fromkeys(payload.get("skipped_activity_ids") or [
                key for key, item in known.items() if item["state"] == "skipped"
            ]))
            if any(item not in known for item in completed + skipped):
                raise IdentityError("VALIDATION_ERROR", "Hoạt động replan không thuộc chuyến đi.", 422)
            actual_spend = session.scalar(select(func.coalesce(func.sum(
                ExpenseEntryModel.amount
            ), Decimal("0"))).where(ExpenseEntryModel.trip_id == trip_id))
            remaining = {
                "completed_activity_ids": completed,
                "skipped_activity_ids": skipped,
                "completed_poi_ids": [
                    known[item]["poi_id"] for item in completed
                    if known[item]["poi_id"]
                ],
                "skipped_poi_ids": [
                    known[item]["poi_id"] for item in skipped
                    if known[item]["poi_id"]
                ],
                "remaining_from": payload.get("remaining_from"),
                "unavailable_poi_ids": list(payload.get("unavailable_poi_ids") or []),
                "changed_constraints": dict(payload.get("changed_constraints") or {}),
                "actual_spend": float(actual_spend or 0),
            }
        return self.create_planning_request(
            principal,
            trip_id,
            idempotency_key,
            target_count=int(payload.get("target_count") or 5),
            constraint_overrides=remaining["changed_constraints"],
            request_kind="replan",
            source_version_id=source_id,
            remaining_context=remaining,
        )
