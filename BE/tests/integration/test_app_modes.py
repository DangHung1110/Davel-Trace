from __future__ import annotations

import pytest

from BE.app.core.config import Settings
from BE.app.modules.planning_evidence.api import create_planning_evidence_service
from BE.app.modules.planning_evidence.infrastructure import LegacyPlanningEvidenceAdapter


def test_demo_without_database_uses_annotated_legacy_adapter(tmp_path) -> None:
    service = create_planning_evidence_service(
        Settings(
            app_mode="demo",
            acceptance_db_path=str(tmp_path / "legacy.db"),
            _env_file=None,
        )
    )
    assert isinstance(service, LegacyPlanningEvidenceAdapter)
    assert service.owner == "platform-foundation"
    assert service.removal_condition


def test_production_cannot_start_without_postgresql() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(
            app_mode="production",
            allowed_origins="https://app.example",
            _env_file=None,
        )


def test_production_rejects_sqlite_url() -> None:
    with pytest.raises(ValueError, match=r"postgresql\+psycopg"):
        Settings(
            app_mode="production",
            database_url="sqlite:///local.db",
            allowed_origins="https://app.example",
            _env_file=None,
        )
