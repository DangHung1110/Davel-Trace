from __future__ import annotations

from alembic import command

from BE.app.core.config import get_settings
from BE.app.db.migrations import alembic_config, get_script_head, inspect_database


def test_upgrade_head_is_repeatable_on_local_postgres() -> None:
    settings = get_settings()
    assert settings.database_url
    command.upgrade(alembic_config(), "head")
    command.upgrade(alembic_config(), "head")
    status = inspect_database(settings.database_url)
    assert status["schema_ready"] is True
    assert status["current_revision"] == get_script_head() == "005_001"


def test_missing_or_failed_revision_cannot_look_ready(monkeypatch) -> None:
    class _Context:
        def get_current_revision(self):
            return None

    monkeypatch.setattr(
        "BE.app.db.migrations.MigrationContext.configure", lambda _connection: _Context()
    )
    settings = get_settings()
    status = inspect_database(settings.database_url)
    assert status["reachable"] is True
    assert status["current_revision"] is None
    assert status["schema_ready"] is False
