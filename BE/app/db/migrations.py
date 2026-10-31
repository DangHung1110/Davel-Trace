"""Read-only schema and connectivity inspection for readiness."""

from __future__ import annotations

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Engine

from BE.app.db.session import create_database_engine


def alembic_config() -> Config:
    return Config("BE/alembic.ini")


def get_script_head() -> str | None:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def get_database_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def inspect_database(database_url: str) -> dict:
    engine = create_database_engine(database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        current = get_database_revision(engine)
        head = get_script_head()
        return {
            "reachable": True,
            "current_revision": current,
            "head_revision": head,
            "schema_ready": current is not None and current == head,
        }
    finally:
        engine.dispose()
