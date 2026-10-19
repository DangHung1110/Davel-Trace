from __future__ import annotations

from sqlalchemy.orm import Session

from BE.app.errors import AppError
from BE.app.models.profile import UserProfile
from BE.app.repositories import profiles as repo
from BE.app.schemas.profile import ProfileCreate, ProfileUpdate


def list_profiles(session: Session) -> tuple[list[UserProfile], str | None]:
    state = repo.get_device_state(session)
    session.commit()
    return repo.list_profiles(session), state.active_profile_id


def get_profile(session: Session, profile_id: str) -> UserProfile:
    profile = repo.get_profile(session, profile_id)
    if profile is None:
        raise AppError("PROFILE_NOT_FOUND", "Không tìm thấy hồ sơ", 404)
    return profile


def create_profile(session: Session, command: ProfileCreate) -> UserProfile:
    profile = UserProfile(**command.model_dump())
    session.add(profile)
    session.flush()
    state = repo.get_device_state(session)
    if state.active_profile_id is None:
        state.active_profile_id = profile.id
    session.commit()
    session.refresh(profile)
    return profile


def update_profile(
    session: Session, profile_id: str, command: ProfileUpdate
) -> UserProfile:
    profile = get_profile(session, profile_id)
    if profile.version != command.version:
        raise AppError(
            "VERSION_CONFLICT",
            "Hồ sơ đã thay đổi; hãy tải lại trước khi lưu",
            409,
            {"expected": command.version, "current": profile.version},
        )
    for field, value in command.model_dump(exclude={"version"}, exclude_none=True).items():
        setattr(profile, field, value)
    profile.version += 1
    session.commit()
    session.refresh(profile)
    return profile


def set_active_profile(session: Session, profile_id: str) -> str:
    get_profile(session, profile_id)
    state = repo.get_device_state(session)
    state.active_profile_id = profile_id
    session.commit()
    return profile_id


def delete_profile(
    session: Session, profile_id: str, version: int, confirm: bool
) -> None:
    profile = get_profile(session, profile_id)
    if profile.version != version:
        raise AppError("VERSION_CONFLICT", "Hồ sơ đã thay đổi; hãy tải lại", 409)
    dependent_count = repo.dependent_trip_count(session, profile_id)
    if dependent_count and not confirm:
        raise AppError(
            "CONFIRMATION_REQUIRED",
            "Xóa hồ sơ sẽ xóa các chuyến đi liên quan",
            409,
            {"trips": dependent_count},
        )
    state = repo.get_device_state(session)
    if state.active_profile_id == profile_id:
        state.active_profile_id = None
    session.delete(profile)
    session.commit()
