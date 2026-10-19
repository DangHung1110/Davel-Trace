from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_builds_management_schema_from_blank_database(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[3]
    database_path = tmp_path / "migration.db"
    url = f"sqlite:///{database_path.as_posix()}"
    config = Config(str(repo_root / "BE" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)

    command.upgrade(config, "head")

    tables = set(inspect(create_engine(url)).get_table_names())
    assert {
        "alembic_version",
        "user_profiles",
        "device_state",
        "trips",
        "itineraries",
        "activities",
        "expenses",
        "route_segments",
    } <= tables

    command.downgrade(config, "base")
    remaining = set(inspect(create_engine(url)).get_table_names())
    assert remaining == {"alembic_version"}
