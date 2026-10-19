from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from BE.app.models.trip import Activity, Itinerary, Trip


def list_trips(session: Session, profile_id: str) -> list[Trip]:
    statement = (
        select(Trip)
        .where(Trip.profile_id == profile_id)
        .order_by(Trip.start_date.desc(), Trip.created_at.desc())
    )
    return list(session.scalars(statement))


def get_trip(session: Session, trip_id: str, *, detail: bool = False) -> Trip | None:
    statement = select(Trip).where(Trip.id == trip_id)
    if detail:
        statement = statement.options(
            selectinload(Trip.itinerary).selectinload(Itinerary.activities),
            selectinload(Trip.expenses),
        )
    return session.scalar(statement)


def get_itinerary(session: Session, trip_id: str) -> Itinerary | None:
    return session.scalar(
        select(Itinerary)
        .where(Itinerary.trip_id == trip_id)
        .options(selectinload(Itinerary.activities))
    )


def get_activity(session: Session, activity_id: str) -> Activity | None:
    return session.scalar(
        select(Activity)
        .where(Activity.id == activity_id)
        .options(selectinload(Activity.itinerary).selectinload(Itinerary.activities))
    )
