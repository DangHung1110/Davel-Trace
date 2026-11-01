"""Explicit, idempotent import of legacy SQLite planning evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from BE.app.core.config import get_settings
from BE.app.db.models import ImportRunModel
from BE.app.db.session import get_session_factory
from BE.app.modules.planning_evidence.infrastructure import (
    PostgresPlanningEvidenceRepository,
)


SOURCE_KIND = "acceptance-sqlite-v1"


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _json(value: str, field: str):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid legacy JSON in {field}") from exc


def _read_rows(path: Path, table: str) -> list[dict]:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]
    finally:
        connection.close()


def import_legacy_sqlite(
    source_path: str | Path,
    session_factory: sessionmaker,
) -> dict:
    source = Path(source_path).resolve()
    if not source.is_file():
        raise FileNotFoundError("legacy SQLite source does not exist")
    fingerprint = _fingerprint(source)
    acceptances = _read_rows(source, "acceptance_records")
    shadows = _read_rows(source, "shadow_observations")

    with session_factory() as session:
        completed = session.scalar(
            select(ImportRunModel).where(
                ImportRunModel.source_kind == SOURCE_KIND,
                ImportRunModel.source_fingerprint == fingerprint,
                ImportRunModel.status == "completed",
            )
        )
        if completed is not None:
            return {
                "already_imported": True,
                "acceptance_count": completed.acceptance_count,
                "shadow_count": completed.shadow_count,
                "source_fingerprint": fingerprint,
            }

    with session_factory() as session:
        with session.begin():
            run = ImportRunModel(
                source_kind=SOURCE_KIND,
                source_fingerprint=fingerprint,
                status="running",
            )
            session.add(run)
            repository = PostgresPlanningEvidenceRepository(session)
            for row in shadows:
                repository.save_shadow(
                    {
                        "observation_id": row["observation_id"],
                        "trip_id": row["trip_id"],
                        "created_at": _timestamp(row["created_at"]),
                        "data_version": row["data_version"],
                        "candidate_ids": _json(
                            row["candidate_ids_json"], "candidate_ids_json"
                        ),
                        "forward": _json(row["forward_json"], "forward_json"),
                        "reverse": _json(row["reverse_json"], "reverse_json"),
                        "consensus": _json(
                            row["consensus_json"], "consensus_json"
                        ),
                        "deterministic_top_id": row["deterministic_top_id"],
                        "shadow_top_id": row["shadow_top_id"],
                        "swap_consistent": bool(row["swap_consistent"]),
                        "length_correlation": row["length_correlation"],
                        "veto_count": row["veto_count"],
                        "status": row["status"],
                        "latency_ms": row["latency_ms"],
                    }
                )
            for row in acceptances:
                imported = repository.save_acceptance(
                    acceptance_id=row["acceptance_id"],
                    idempotency_key=row["idempotency_key"],
                    itinerary_id=row["itinerary_id"],
                    trip_id=row["trip_id"],
                    parent_acceptance_id=row["parent_acceptance_id"],
                    selected_at=_timestamp(row["selected_at"]),
                    schema_version=row["schema_version"],
                    data_version=row["data_version"],
                    request=_json(row["request_json"], "request_json"),
                    plan=_json(row["plan_json"], "plan_json"),
                    gate=_json(row["gate_json"], "gate_json"),
                    deterministic_rank=row["deterministic_rank"],
                    deterministic_score=row["deterministic_score"],
                    shadow_observation_id=row["shadow_observation_id"],
                )
                if imported["acceptance_id"] != row["acceptance_id"]:
                    raise ValueError("conflicting legacy idempotency key")
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.acceptance_count = len(acceptances)
            run.shadow_count = len(shadows)

    return {
        "already_imported": False,
        "acceptance_count": len(acceptances),
        "shadow_count": len(shadows),
        "source_fingerprint": fingerprint,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required for import")
    result = import_legacy_sqlite(
        args.source,
        get_session_factory(settings.database_url),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
