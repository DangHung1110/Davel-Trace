"""Profile application use cases."""

from datetime import datetime, timezone

from BE.app.core.config import get_settings
from BE.app.db.models import TravelerProfileModel
from BE.app.db.session import session_scope
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.profiles.domain import normalized_profile, profile_snapshot
from BE.app.modules.profiles.infrastructure import owned_profile


def public(profile) -> dict:
    if profile is None:
        return {"profile": None}
    return {"profile": {
        "id": str(profile.account_id), "display_name": profile.display_name,
        **profile_snapshot(profile),
        "spending_level": {"saver": 1, "balanced": 2, "comfort": 3}.get(
            profile.spending_style, 2
        ),
        "onboarding_complete": profile.onboarding_complete,
        "version": profile.version, "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }}


class ProfileService:
    def read(self, principal):
        with session_scope(get_settings().database_url) as session:
            return public(owned_profile(session, principal.account_id))

    def save(self, principal, data: dict, expected_version: int | None):
        try:
            clean = normalized_profile(data)
        except (ValueError, TypeError) as exc:
            raise IdentityError("VALIDATION_ERROR", str(exc), 422) from exc
        with session_scope(get_settings().database_url) as session:
            profile = owned_profile(session, principal.account_id, lock=True)
            if profile is None:
                if expected_version is not None:
                    raise IdentityError("VERSION_CONFLICT", "Hồ sơ đã thay đổi.", 409)
                profile = TravelerProfileModel(account_id=principal.account_id, **clean)
                session.add(profile)
            else:
                if expected_version != profile.version:
                    raise IdentityError("VERSION_CONFLICT", "Hồ sơ đã thay đổi trên thiết bị khác.", 409)
                for key, value in clean.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                profile.version += 1
                profile.updated_at = datetime.now(timezone.utc)
            session.flush()
            return public(profile)

    def reset(self, principal, expected_version: int):
        with session_scope(get_settings().database_url) as session:
            profile = owned_profile(session, principal.account_id, lock=True)
            if not profile:
                raise IdentityError("NOT_FOUND", "Chưa có hồ sơ.", 404)
            if profile.version != expected_version:
                raise IdentityError("VERSION_CONFLICT", "Hồ sơ đã thay đổi.", 409)
            profile.food_preferences = []
            profile.preferred_activities = []
            profile.usual_transport = []
            profile.pace = profile.fitness = 2
            profile.spending_style = "balanced"
            profile.version += 1
            profile.updated_at = datetime.now(timezone.utc)
            session.flush()
            return public(profile)
