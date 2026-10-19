from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from BE.app.errors import AppError
from BE.app.models.route import RouteSegment
from BE.app.models.trip import Activity, Itinerary
from BE.app.repositories import trips as repo
from BE.app.schemas.trip import ActivityCreate, ActivityOrder, ActivityUpdate


def get_itinerary(session: Session, trip_id: str) -> Itinerary:
    itinerary = repo.get_itinerary(session, trip_id)
    if itinerary is None:
        raise AppError("ITINERARY_NOT_FOUND", "Không tìm thấy lịch trình", 404)
    return itinerary


def get_activity(session: Session, activity_id: str) -> Activity:
    activity = repo.get_activity(session, activity_id)
    if activity is None:
        raise AppError("ACTIVITY_NOT_FOUND", "Không tìm thấy hoạt động", 404)
    return activity


def _check_itinerary_version(itinerary: Itinerary, expected: int) -> None:
    if itinerary.version != expected:
        raise AppError(
            "VERSION_CONFLICT",
            "Lịch trình đã thay đổi; hãy tải lại",
            409,
            {"expected": expected, "current": itinerary.version},
        )


def _validate_activity_time(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise AppError("INVALID_ACTIVITY_TIME", "Giờ kết thúc phải sau giờ bắt đầu", 422)


def _invalidate_routes(session: Session, trip_id: str) -> None:
    session.execute(delete(RouteSegment).where(RouteSegment.trip_id == trip_id))


def _rewrite_positions(session: Session, activities: list[Activity]) -> None:
    # Move every row through a valid, collision-free range before assigning the
    # final dense order. SQLite enforces both the non-negative check and the
    # unique (itinerary_id, position) constraint on each UPDATE statement.
    for index, activity in enumerate(activities):
        activity.position = 1_000_000 + index
    session.flush()
    for index, activity in enumerate(activities):
        activity.position = index


def add_activity(
    session: Session, trip_id: str, command: ActivityCreate
) -> Itinerary:
    itinerary = get_itinerary(session, trip_id)
    _check_itinerary_version(itinerary, command.itinerary_version)
    activities = sorted(itinerary.activities, key=lambda item: item.position)
    position = command.position if command.position is not None else len(activities)
    position = min(position, len(activities))
    values = command.model_dump(exclude={"itinerary_version", "position"})
    activity = Activity(
        position=len(activities),
        source="manual",
        **values,
    )
    itinerary.activities.append(activity)
    session.flush()
    activities.insert(position, activity)
    _rewrite_positions(session, activities)
    itinerary.version += 1
    _invalidate_routes(session, trip_id)
    session.commit()
    return get_itinerary(session, trip_id)


def update_activity(
    session: Session, activity_id: str, command: ActivityUpdate
) -> Itinerary:
    activity = get_activity(session, activity_id)
    itinerary = activity.itinerary
    _check_itinerary_version(itinerary, command.itinerary_version)
    if activity.version != command.version:
        raise AppError("VERSION_CONFLICT", "Hoạt động đã thay đổi; hãy tải lại", 409)
    values = command.model_dump(
        exclude={"version", "itinerary_version"}, exclude_none=True
    )
    start_at = values.get("start_at", activity.start_at)
    end_at = values.get("end_at", activity.end_at)
    _validate_activity_time(start_at, end_at)
    for field, value in values.items():
        setattr(activity, field, value)
    activity.version += 1
    itinerary.version += 1
    _invalidate_routes(session, itinerary.trip_id)
    session.commit()
    return get_itinerary(session, itinerary.trip_id)


def delete_activity(
    session: Session, activity_id: str, version: int, itinerary_version: int
) -> Itinerary:
    activity = get_activity(session, activity_id)
    itinerary = activity.itinerary
    _check_itinerary_version(itinerary, itinerary_version)
    if activity.version != version:
        raise AppError("VERSION_CONFLICT", "Hoạt động đã thay đổi; hãy tải lại", 409)
    trip_id = itinerary.trip_id
    remaining = [item for item in itinerary.activities if item.id != activity_id]
    session.delete(activity)
    session.flush()
    _rewrite_positions(session, remaining)
    itinerary.version += 1
    _invalidate_routes(session, trip_id)
    session.commit()
    return get_itinerary(session, trip_id)


def reorder_activities(
    session: Session, trip_id: str, command: ActivityOrder
) -> Itinerary:
    itinerary = get_itinerary(session, trip_id)
    _check_itinerary_version(itinerary, command.itinerary_version)
    by_id = {activity.id: activity for activity in itinerary.activities}
    if len(command.activity_ids) != len(by_id) or set(command.activity_ids) != set(by_id):
        raise AppError(
            "ORDER_MISMATCH", "Danh sách sắp xếp phải chứa đúng mọi hoạt động", 400
        )
    _rewrite_positions(session, [by_id[activity_id] for activity_id in command.activity_ids])
    itinerary.version += 1
    _invalidate_routes(session, trip_id)
    session.commit()
    return get_itinerary(session, trip_id)


def overlap_warnings(itinerary: Itinerary) -> list[dict]:
    activities = sorted(itinerary.activities, key=lambda item: item.start_at)
    warnings: list[dict] = []
    for index, first in enumerate(activities):
        for second in activities[index + 1 :]:
            if second.start_at >= first.end_at:
                break
            warnings.append(
                {
                    "activity_ids": [first.id, second.id],
                    "message": f"{first.title} và {second.title} đang chồng giờ",
                }
            )
    return warnings


def itinerary_payload(itinerary: Itinerary) -> dict:
    from BE.app.schemas.trip import ActivityRead

    return {
        "id": itinerary.id,
        "trip_id": itinerary.trip_id,
        "version": itinerary.version,
        "source": itinerary.source,
        "status": itinerary.status,
        "activities": [
            ActivityRead.model_validate(item).model_dump(mode="json")
            for item in sorted(itinerary.activities, key=lambda item: item.position)
        ],
        "warnings": overlap_warnings(itinerary),
        "created_at": itinerary.created_at,
        "updated_at": itinerary.updated_at,
    }
