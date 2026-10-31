"""Restore a backup into a temporary PostgreSQL database, verify, then drop it."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from sqlalchemy.engine import make_url

from BE.app.core.config import get_settings
from BE.scripts.backup_database import collect_database_evidence
from BE.scripts.verify_backup import verify_manifest, verify_restored_evidence


_SAFE_DATABASE = re.compile(r"^[a-z][a-z0-9_]{2,62}$")


def _compose_postgres(*args: str, stdin=None) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            "BE/.env",
            "exec",
            "-T",
            "postgres",
            *args,
        ],
        check=True,
        stdin=stdin,
    )


def restore_and_verify(
    database_url: str,
    archive_path: str | Path,
    manifest_path: str | Path,
    restore_database: str = "davel_trace_restore_check",
) -> dict:
    if not _SAFE_DATABASE.fullmatch(restore_database):
        raise ValueError("restore database name is not safe")
    source_url = make_url(database_url)
    if restore_database == source_url.database:
        raise ValueError("restore database must differ from the source database")
    manifest = verify_manifest(archive_path, manifest_path)
    user = source_url.username or ""
    _compose_postgres("dropdb", "--if-exists", "--username", user, restore_database)
    try:
        _compose_postgres("createdb", "--username", user, restore_database)
        with Path(archive_path).open("rb") as archive:
            _compose_postgres(
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "--no-acl",
                "--username",
                user,
                "--dbname",
                restore_database,
                stdin=archive,
            )
        restored_url = source_url.set(database=restore_database).render_as_string(
            hide_password=False
        )
        actual = collect_database_evidence(restored_url)
        verify_restored_evidence(manifest, actual)
        return actual
    finally:
        _compose_postgres("dropdb", "--if-exists", "--username", user, restore_database)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--database", default="davel_trace_restore_check")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required for restore verification")
    result = restore_and_verify(
        settings.database_url,
        args.archive,
        args.manifest,
        args.database,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
