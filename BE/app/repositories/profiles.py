from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from BE.app.models.profile import DeviceState, UserProfile
from BE.app.models.trip import Trip


def list_profiles(session: Session) -> list[UserProfile]:
    return list(session.scalars(select(UserProfile).order_by(UserProfile.created_at)))


def get_profile(session: Session, profile_id: str) -> UserProfile | None:
    return session.get(UserProfile, profile_id)


def get_device_state(session: Session) -> DeviceState:
    state = session.get(DeviceState, 1)
    if state is None:
        state = DeviceState(id=1)
        session.add(state)
        session.flush()
    return state


def dependent_trip_count(session: Session, profile_id: str) -> int:
    return int(
        session.scalar(select(func.count(Trip.id)).where(Trip.profile_id == profile_id))
        or 0
    )
