"""Create a PostgreSQL custom archive and checksum manifest outside Git."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from BE.app.core.config import get_settings
from BE.app.db.migrations import get_script_head
from BE.scripts.verify_backup import sha256_file


_EVIDENCE_TABLES = (
    "acceptance_records",
    "shadow_observations",
    "import_runs",
    "seed_runs",
)


def collect_database_evidence(database_url: str) -> dict:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            counts = {
                table: int(
                    connection.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one()
                )
                for table in _EVIDENCE_TABLES
            }
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            representative = {
                "acceptance_id": connection.execute(
                    text(
                        "SELECT CAST(acceptance_id AS TEXT) FROM acceptance_records "
                        "ORDER BY acceptance_id LIMIT 1"
                    )
                ).scalar_one_or_none(),
                "observation_id": connection.execute(
                    text(
                        "SELECT CAST(observation_id AS TEXT) FROM shadow_observations "
                        "ORDER BY observation_id LIMIT 1"
                    )
                ).scalar_one_or_none(),
            }
            relationship_row = connection.execute(
                text(
                    "SELECT CAST(acceptance_id AS TEXT) AS acceptance_id, "
                    "CAST(parent_acceptance_id AS TEXT) AS parent_acceptance_id, "
                    "CAST(shadow_observation_id AS TEXT) AS shadow_observation_id, "
                    "trip_id, itinerary_id FROM acceptance_records "
                    "ORDER BY acceptance_id LIMIT 1"
                )
            ).mappings().first()
            relationships = (
                dict(relationship_row)
                if relationship_row is not None
                else {
                    "acceptance_id": None,
                    "parent_acceptance_id": None,
                    "shadow_observation_id": None,
                    "trip_id": None,
                    "itinerary_id": None,
                }
            )
        return {
            "schema_revision": revision,
            "counts": counts,
            "representative": representative,
            "relationships": relationships,
        }
    finally:
        engine.dispose()


def _docker_pg_dump_command(url) -> list[str]:
    return [
        "docker",
        "compose",
        "--env-file",
        "BE/.env",
        "exec",
        "-T",
        "postgres",
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--username",
        url.username or "",
        url.database or "",
    ]


def create_backup(database_url: str, destination: str | Path) -> dict:
    url = make_url(database_url)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PGPASSWORD"] = url.password or ""
    dump_source = "host-pg-dump"
    if shutil.which("pg_dump"):
        command = [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--host",
            url.host or "localhost",
            "--port",
            str(url.port or 5432),
            "--username",
            url.username or "",
            "--file",
            str(destination),
            url.database or "",
        ]
        subprocess.run(command, check=True, env=env)
    else:
        dump_source = "docker-compose"
        with destination.open("wb") as archive:
            subprocess.run(
                _docker_pg_dump_command(url),
                check=True,
                stdout=archive,
            )
    if destination.stat().st_size == 0:
        raise RuntimeError("pg_dump created an empty archive")
    evidence = collect_database_evidence(database_url)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": sha256_file(destination),
        "schema_revision": evidence["schema_revision"] or get_script_head(),
        "counts": evidence["counts"],
        "representative": evidence["representative"],
        "relationships": evidence["relationships"],
        "database_label": url.database,
        "format": "postgresql-custom",
        "dump_source": dump_source,
    }
    manifest_path = destination.with_suffix(destination.suffix + ".json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {**manifest, "manifest_path": str(manifest_path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required for backup")
    print(
        json.dumps(
            create_backup(settings.database_url, args.output),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
