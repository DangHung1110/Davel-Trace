from __future__ import annotations

from sqlalchemy.orm import Session

from BE.app.errors import AppError
from BE.app.models.profile import UserProfile
from BE.app.models.trip import Itinerary, Trip
from BE.app.repositories import trips as repo
from BE.app.schemas.trip import TripCreate, TripUpdate


def _validate_range(trip: Trip, updates: dict) -> None:
    start_date = updates.get("start_date", trip.start_date)
    end_date = updates.get("end_date", trip.end_date)
    day_start = updates.get("day_start", trip.day_start)
    day_end = updates.get("day_end", trip.day_end)
    days = (end_date - start_date).days
    if days < 0 or days > 1 or (days == 0 and day_end <= day_start):
        raise AppError(
            "INVALID_DATE_RANGE", "Chuyến đi chỉ hỗ trợ một hoặc hai ngày", 422
        )


def get_trip(session: Session, trip_id: str, *, detail: bool = False) -> Trip:
    trip = repo.get_trip(session, trip_id, detail=detail)
    if trip is None:
        raise AppError("TRIP_NOT_FOUND", "Không tìm thấy chuyến đi", 404)
    return trip


def list_trips(session: Session, profile_id: str) -> list[Trip]:
    if session.get(UserProfile, profile_id) is None:
        raise AppError("PROFILE_NOT_FOUND", "Không tìm thấy hồ sơ", 404)
    return repo.list_trips(session, profile_id)


def create_trip(session: Session, command: TripCreate) -> Trip:
    if session.get(UserProfile, command.profile_id) is None:
        raise AppError("PROFILE_NOT_FOUND", "Không tìm thấy hồ sơ", 404)
    trip = Trip(**command.model_dump())
    trip.itinerary = Itinerary(source="manual", status="active", version=1)
    session.add(trip)
    session.commit()
    session.refresh(trip)
    return trip


def update_trip(session: Session, trip_id: str, command: TripUpdate) -> Trip:
    trip = get_trip(session, trip_id)
    if trip.version != command.version:
        raise AppError("VERSION_CONFLICT", "Chuyến đi đã thay đổi; hãy tải lại", 409)
    values = command.model_dump(exclude={"version"}, exclude_none=True)
    _validate_range(trip, values)
    for field, value in values.items():
        setattr(trip, field, value)
    trip.version += 1
    session.commit()
    session.refresh(trip)
    return trip


def delete_trip(session: Session, trip_id: str, version: int, confirm: bool) -> None:
    trip = get_trip(session, trip_id)
    if trip.version != version:
        raise AppError("VERSION_CONFLICT", "Chuyến đi đã thay đổi; hãy tải lại", 409)
    if not confirm:
        raise AppError(
            "CONFIRMATION_REQUIRED",
            "Xóa chuyến đi sẽ xóa lịch trình và chi tiêu liên quan",
            409,
            {
                "activities": len(trip.itinerary.activities) if trip.itinerary else 0,
                "expenses": len(trip.expenses),
            },
        )
    session.delete(trip)
    session.commit()
