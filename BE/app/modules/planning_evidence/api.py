"""Public composition entry point for the planning-evidence capability."""

from __future__ import annotations

from BE.app.core.config import AppMode, Settings
from BE.app.db.session import get_session_factory
from BE.app.modules.planning_evidence.infrastructure import (
    LegacyPlanningEvidenceAdapter,
    create_postgres_planning_evidence_service,
)


def create_planning_evidence_service(settings: Settings):
    if settings.database_url:
        return create_postgres_planning_evidence_service(
            get_session_factory(settings.database_url)
        )
    if settings.app_mode is AppMode.production:
        raise RuntimeError("authoritative database is required")
    return LegacyPlanningEvidenceAdapter(settings.acceptance_db_path)
