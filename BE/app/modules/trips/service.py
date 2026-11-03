"""Transactional trip management use cases."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select

from BE.app.core.config import get_settings
from BE.app.core.request_context import get_correlation_id
from BE.app.db.models import (ActiveTripSelectionModel, MutationReceiptModel,
    TravelerProfileModel, TripActivityModel, TripDayModel, TripLifecycleEventModel, TripModel)
from BE.app.db.session import session_scope
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.expenses.infrastructure import record_budget_revision
from BE.app.modules.profiles.domain import profile_snapshot
from BE.app.modules.trips.domain import dates_between, validate_trip
from BE.app.modules.trips.infrastructure import owned_trip, receipt, request_fingerprint, save_receipt


def activity_public(row) -> dict:
    return {"id": str(row.activity_id), "day_id": str(row.day_id), "kind": row.kind,
            "poi_id": row.poi_id, "title": row.title,
            "start_time": row.start_time.isoformat() if row.start_time else None,
            "end_time": row.end_time.isoformat() if row.end_time else None,
            "duration_minutes": row.duration_minutes,
            "estimated_cost": float(row.estimated_cost) if row.estimated_cost is not None else None,
            "currency": row.currency, "status": row.progress_state, "position": row.position,
            "notes": row.notes, "version": row.version}


def overlap_warnings(activities) -> list[str]:
    timed = sorted(
        (item for item in activities if item.start_time and item.end_time),
        key=lambda item: (item.start_time, item.position),
    )
    warnings = []
    for previous, current in zip(timed, timed[1:]):
        if current.start_time < previous.end_time:
            warnings.append(
                f"{previous.title} trùng thời gian với {current.title}."
            )
    return warnings


def trip_public(session, row, *, include_days=True) -> dict:
    result = {"id": str(row.trip_id), "title": row.title, "destination": row.destination,
              "start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat(),
              "traveler_count": row.traveler_count, "progress_state": row.progress_state,
              "lifecycle_state": row.lifecycle_state, "review_state": row.review_state,
              "indicative_budget": float(row.indicative_budget) if row.indicative_budget is not None else None,
              "currency": row.currency, "preferred_transport": row.preferred_transport,
              "day_start": row.day_start.isoformat(), "day_end": row.day_end.isoformat(),
              "notes": row.notes, "profile_version": row.profile_version,
              "profile_snapshot": row.profile_snapshot, "preference_overrides": row.preference_overrides,
              "version": row.version, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}
    if include_days:
        days = list(session.scalars(select(TripDayModel).where(TripDayModel.trip_id == row.trip_id).order_by(TripDayModel.position)))
        result["days"] = []
        for day in days:
            activities = list(session.scalars(select(TripActivityModel).where(
                TripActivityModel.day_id == day.day_id
            ).order_by(TripActivityModel.position)))
            result["days"].append({
                "id": str(day.day_id),
                "date": day.local_date.isoformat(),
                "position": day.position,
                "version": day.version,
                "activities": [activity_public(item) for item in activities],
                "warnings": overlap_warnings(activities),
            })
    return result


class TripService:
    def list(self, principal, q="", state=None):
        with session_scope(get_settings().database_url) as session:
            query = select(TripModel).where(TripModel.account_id == principal.account_id)
            today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
            active = session.get(ActiveTripSelectionModel, principal.account_id)
            if not state or state == "available":
                query = query.where(TripModel.lifecycle_state == "available")
            elif state == "active":
                query = query.where(
                    TripModel.lifecycle_state == "available",
                    TripModel.trip_id == (active.trip_id if active else None),
                )
            elif state == "upcoming":
                query = query.where(
                    TripModel.lifecycle_state == "available",
                    TripModel.start_date > today,
                )
            elif state == "completed":
                query = query.where(
                    TripModel.lifecycle_state == "available",
                    TripModel.end_date < today,
                )
            elif state in ("archived", "deleted"):
                query = query.where(TripModel.lifecycle_state == state)
            else:
                raise IdentityError("VALIDATION_ERROR", "Bộ lọc chuyến đi không hợp lệ.", 422)
            if q.strip():
                query = query.where(func.lower(TripModel.title).contains(q.strip().lower()))
            rows = list(session.scalars(query.order_by(TripModel.updated_at.desc(), TripModel.trip_id)))
            return {"items": [trip_public(session, row, include_days=False) for row in rows],
                    "active_trip_id": str(active.trip_id) if active and active.trip_id else None,
                    "selection_version": active.version if active else 0}

    def get(self, principal, trip_id, include_deleted=False):
        with session_scope(get_settings().database_url) as session:
            return trip_public(session, owned_trip(session, principal.account_id, trip_id, include_deleted=include_deleted))

    def create(self, principal, data, key):
        try: validate_trip(data)
        except (ValueError, TypeError) as exc: raise IdentityError("VALIDATION_ERROR", str(exc), 422) from exc
        fingerprint = request_fingerprint(data)
        with session_scope(get_settings().database_url) as session:
            old, key_hash = receipt(session, principal.account_id, "trip.create", "root", key, fingerprint)
            if old: return trip_public(session, owned_trip(session, principal.account_id, UUID(old.result_resource_id)))
            profile = session.get(TravelerProfileModel, principal.account_id)
            if not profile: raise IdentityError("PROFILE_REQUIRED", "Hãy hoàn tất hồ sơ trước.", 409)
            row = TripModel(account_id=principal.account_id, title=data["title"].strip(),
                start_date=data["start_date"], end_date=data["end_date"], traveler_count=data["traveler_count"],
                indicative_budget=data.get("indicative_budget"), preferred_transport=data.get("preferred_transport", "mixed"),
                day_start=data["day_start"], day_end=data["day_end"], notes=data.get("notes", "")[:2000],
                profile_version=profile.version, profile_snapshot=profile_snapshot(profile),
                preference_overrides=data.get("preference_overrides") or {})
            session.add(row); session.flush()
            for index, local_date in enumerate(dates_between(row.start_date, row.end_date)):
                session.add(TripDayModel(trip_id=row.trip_id, local_date=local_date, position=index))
            save_receipt(session, principal.account_id, "trip.create", "root", key_hash, fingerprint, row.trip_id, 201)
            session.add(TripLifecycleEventModel(
                trip_id=row.trip_id,
                account_id=principal.account_id,
                event_type="created",
                outcome="success",
                correlation_id=get_correlation_id(),
                metadata_json={"version": row.version},
            ))
            session.flush(); return trip_public(session, row)

    def update(self, principal, trip_id, data, expected_version, confirm_removed=False):
        with session_scope(get_settings().database_url) as session:
            row = owned_trip(session, principal.account_id, trip_id, lock=True)
            if row.version != expected_version: raise IdentityError("VERSION_CONFLICT", "Chuyến đi đã thay đổi.", 409)
            merged = {"title": data.get("title", row.title), "start_date": data.get("start_date", row.start_date),
                "end_date": data.get("end_date", row.end_date), "traveler_count": data.get("traveler_count", row.traveler_count),
                "day_start": data.get("day_start", row.day_start), "day_end": data.get("day_end", row.day_end),
                "preference_overrides": data.get("preference_overrides", row.preference_overrides)}
            try: validate_trip(merged)
            except (ValueError, TypeError) as exc: raise IdentityError("VALIDATION_ERROR", str(exc), 422) from exc
            keep_dates = set(dates_between(merged["start_date"], merged["end_date"]))
            days = list(session.scalars(select(TripDayModel).where(TripDayModel.trip_id == row.trip_id).with_for_update()))
            removed = [d for d in days if d.local_date not in keep_dates]
            populated = any(session.scalar(select(func.count()).select_from(TripActivityModel).where(TripActivityModel.day_id == d.day_id)) for d in removed)
            if populated and not confirm_removed: raise IdentityError("DATE_REDUCTION_CONFIRMATION_REQUIRED", "Việc đổi ngày sẽ xóa hoạt động.", 409)
            for d in removed:
                session.delete(d)
            session.flush()
            existing = {d.local_date for d in days if d.local_date in keep_dates}
            max_position = max((d.position for d in days if d.local_date in keep_dates), default=-1)
            for offset, dt in enumerate(sorted(keep_dates - existing), start=1):
                session.add(TripDayModel(
                    trip_id=row.trip_id,
                    local_date=dt,
                    position=max_position + offset,
                ))
            session.flush()
            ordered = list(session.scalars(select(TripDayModel).where(TripDayModel.trip_id == row.trip_id).order_by(TripDayModel.local_date)))
            temporary_base = max((day.position for day in ordered), default=-1) + 1
            for index, day in enumerate(ordered):
                day.position = temporary_base + index
            session.flush()
            for index, day in enumerate(ordered):
                day.position = index
            if "indicative_budget" in data:
                record_budget_revision(
                    session, row, principal.account_id, data["indicative_budget"],
                    data.get("budget_change_reason", "Cập nhật trong thông tin chuyến đi"),
                )
            for field in ("title","start_date","end_date","traveler_count","day_start","day_end","preference_overrides","preferred_transport","notes"):
                if field in data: setattr(row, field, data[field])
            row.version += 1; row.updated_at = datetime.now(timezone.utc)
            session.flush(); return trip_public(session, row)

    def set_active(self, principal, trip_id, expected_version):
        with session_scope(get_settings().database_url) as session:
            selection = session.get(ActiveTripSelectionModel, principal.account_id, with_for_update=True)
            current_version = selection.version if selection else 0
            if expected_version != current_version:
                if selection and expected_version == current_version - 1 and selection.trip_id == trip_id:
                    return {"active_trip_id": str(selection.trip_id) if selection.trip_id else None,
                            "version": selection.version}
                raise IdentityError("ACTIVE_SELECTION_CONFLICT", "Chuyến đi đang dùng đã thay đổi.", 409)
            if trip_id is not None:
                trip = owned_trip(session, principal.account_id, trip_id)
                if trip.lifecycle_state != "available": raise IdentityError("STATE_CONFLICT", "Chuyến đi không thể kích hoạt.", 409)
            if selection is None:
                selection = ActiveTripSelectionModel(account_id=principal.account_id, trip_id=trip_id)
                session.add(selection)
            else:
                selection.trip_id = trip_id; selection.version += 1; selection.updated_at = datetime.now(timezone.utc)
            session.flush(); return {"active_trip_id": str(selection.trip_id) if selection.trip_id else None, "version": selection.version}

    def lifecycle(self, principal, trip_id, action, expected_version):
        with session_scope(get_settings().database_url) as session:
            row = owned_trip(session, principal.account_id, trip_id, lock=True, include_deleted=True)
            now = datetime.now(timezone.utc)
            if ((action == "archive" and row.lifecycle_state == "archived") or
                    (action == "restore" and row.lifecycle_state == "available") or
                    (action == "delete" and row.lifecycle_state == "deleted")) and expected_version in (row.version, row.version - 1):
                return trip_public(session, row)
            if row.version != expected_version: raise IdentityError("VERSION_CONFLICT", "Chuyến đi đã thay đổi.", 409)
            if action == "archive" and row.lifecycle_state == "available": row.lifecycle_state, row.archived_at = "archived", now
            elif action == "restore" and row.lifecycle_state in ("archived", "deleted"):
                if row.lifecycle_state == "deleted" and row.purge_after and row.purge_after <= now: raise IdentityError("STATE_CONFLICT", "Đã hết thời gian khôi phục.", 409)
                row.lifecycle_state, row.archived_at, row.deleted_at, row.purge_after = "available", None, None, None
            elif action == "delete" and row.lifecycle_state in ("available", "archived"):
                row.lifecycle_state, row.deleted_at, row.purge_after = "deleted", now, now + timedelta(days=30)
            else: raise IdentityError("STATE_CONFLICT", "Trạng thái chuyến đi không phù hợp.", 409)
            selection = session.get(ActiveTripSelectionModel, principal.account_id, with_for_update=True)
            if selection and selection.trip_id == row.trip_id and action in ("archive", "delete"):
                selection.trip_id = None; selection.version += 1
            row.version += 1; row.updated_at = now
            session.add(TripLifecycleEventModel(trip_id=row.trip_id, account_id=principal.account_id,
                event_type=action, outcome="success", correlation_id=get_correlation_id(), metadata_json={"version": row.version}))
            session.flush(); return trip_public(session, row)

    def add_activity(self, principal, trip_id, day_id, data, key):
        with session_scope(get_settings().database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id)
            day = session.scalar(select(TripDayModel).where(TripDayModel.day_id == day_id, TripDayModel.trip_id == trip.trip_id).with_for_update())
            if not day: raise IdentityError("NOT_FOUND", "Không tìm thấy ngày.", 404)
            fingerprint = request_fingerprint(data); old, key_hash = receipt(session, principal.account_id, "activity.create", str(day_id), key, fingerprint)
            if old:
                activity = session.get(TripActivityModel, UUID(old.result_resource_id)); return activity_public(activity)
            title = str(data.get("title", "")).strip()
            if not title: raise IdentityError("VALIDATION_ERROR", "Tên hoạt động là bắt buộc.", 422)
            start, end = data.get("start_time"), data.get("end_time")
            if start and end and start >= end: raise IdentityError("VALIDATION_ERROR", "Thời gian hoạt động không hợp lệ.", 422)
            if ((start and start < trip.day_start) or
                    (end and end > trip.day_end)):
                raise IdentityError("VALIDATION_ERROR", "Hoạt động nằm ngoài khung giờ của chuyến đi.", 422)
            position = session.scalar(select(func.count()).select_from(TripActivityModel).where(TripActivityModel.day_id == day.day_id)) or 0
            row = TripActivityModel(day_id=day.day_id, title=title, kind=data.get("kind", "custom"), poi_id=data.get("poi_id"),
                start_time=start, end_time=end, duration_minutes=data.get("duration_minutes"), estimated_cost=data.get("estimated_cost"),
                notes=str(data.get("notes", ""))[:2000], position=position)
            session.add(row); session.flush(); save_receipt(session, principal.account_id, "activity.create", str(day_id), key_hash, fingerprint, row.activity_id, 201)
            day.version += 1; session.flush(); return activity_public(row)

    def reorder(self, principal, trip_id, day_id, ids, expected_version):
        with session_scope(get_settings().database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id)
            day = session.scalar(select(TripDayModel).where(TripDayModel.day_id == day_id, TripDayModel.trip_id == trip.trip_id).with_for_update())
            if not day: raise IdentityError("NOT_FOUND", "Không tìm thấy ngày.", 404)
            rows = list(session.scalars(select(TripActivityModel).where(TripActivityModel.day_id == day.day_id).with_for_update()))
            mapping = {str(row.activity_id): row for row in rows}
            if len(ids) != len(mapping) or set(ids) != set(mapping): raise IdentityError("VALIDATION_ERROR", "Danh sách sắp xếp không đầy đủ.", 422)
            current_order = [str(row.activity_id) for row in sorted(rows, key=lambda item: item.position)]
            if day.version == expected_version + 1 and current_order == ids:
                return {"id": str(day.day_id), "version": day.version,
                        "activities": [activity_public(mapping[item]) for item in ids]}
            if day.version != expected_version:
                raise IdentityError("VERSION_CONFLICT", "Danh sách hoạt động đã thay đổi.", 409)
            # Avoid transient unique collisions by moving positions out of range first.
            for index, row in enumerate(rows): row.position = len(rows) + index
            session.flush()
            for index, item in enumerate(ids): mapping[item].position = index
            day.version += 1; session.flush()
            return {"id": str(day.day_id), "version": day.version, "activities": [activity_public(mapping[item]) for item in ids]}

    def update_activity(self, principal, activity_id, data, expected_version):
        with session_scope(get_settings().database_url) as session:
            row = session.get(TripActivityModel, activity_id, with_for_update=True)
            if not row:
                raise IdentityError("NOT_FOUND", "Không tìm thấy hoạt động.", 404)
            day = session.get(TripDayModel, row.day_id)
            trip = owned_trip(session, principal.account_id, day.trip_id)
            if row.version != expected_version:
                raise IdentityError("VERSION_CONFLICT", "Hoạt động đã thay đổi.", 409)
            start, end = data.get("start_time", row.start_time), data.get("end_time", row.end_time)
            if start and end and start >= end:
                raise IdentityError("VALIDATION_ERROR", "Thời gian hoạt động không hợp lệ.", 422)
            if ((start and start < trip.day_start) or
                    (end and end > trip.day_end)):
                raise IdentityError("VALIDATION_ERROR", "Hoạt động nằm ngoài khung giờ của chuyến đi.", 422)
            for field in ("title", "kind", "poi_id", "start_time", "end_time", "duration_minutes", "estimated_cost", "notes", "progress_state"):
                if field in data and data[field] is not None:
                    setattr(row, field, data[field])
            if not row.title.strip():
                raise IdentityError("VALIDATION_ERROR", "Tên hoạt động là bắt buộc.", 422)
            row.version += 1; row.updated_at = datetime.now(timezone.utc); day.version += 1
            session.flush(); return activity_public(row)

    def delete_activity(self, principal, activity_id, expected_version):
        with session_scope(get_settings().database_url) as session:
            row = session.get(TripActivityModel, activity_id, with_for_update=True)
            if not row:
                raise IdentityError("NOT_FOUND", "Không tìm thấy hoạt động.", 404)
            day = session.get(TripDayModel, row.day_id, with_for_update=True)
            owned_trip(session, principal.account_id, day.trip_id)
            if row.version != expected_version:
                raise IdentityError("VERSION_CONFLICT", "Hoạt động đã thay đổi.", 409)
            position = row.position; session.delete(row); session.flush()
            remaining = list(session.scalars(select(TripActivityModel).where(
                TripActivityModel.day_id == day.day_id, TripActivityModel.position > position).order_by(TripActivityModel.position).with_for_update()))
            temporary_base = max((item.position for item in remaining), default=position) + 1
            for index, item in enumerate(remaining):
                item.position = temporary_base + index
            session.flush()
            for index, item in enumerate(remaining):
                item.position = position + index
            day.version += 1; session.flush()
            return {"id": str(day.day_id), "version": day.version,
                    "activities": [activity_public(a) for a in session.scalars(select(TripActivityModel).where(
                        TripActivityModel.day_id == day.day_id).order_by(TripActivityModel.position))]}
