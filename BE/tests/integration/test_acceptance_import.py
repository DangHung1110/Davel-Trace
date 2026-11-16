from __future__ import annotations

import sqlite3
from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from BE.app.db.base import Base
from BE.app.db.models import AcceptanceRecordModel, ImportRunModel
from BE.app.services.acceptance_store import AcceptanceStore
from BE.scripts.import_acceptance_sqlite import import_legacy_sqlite


def _legacy_source(tmp_path):
    source = tmp_path / "accepted.db"
    legacy = AcceptanceStore(str(source))
    row = legacy.save_acceptance(
        idempotency_key="legacy-import-001",
        itinerary_id="it-1",
        trip_id="trip-1",
        data_version="danang-v1",
        request={"budget": 10},
        plan={"activities": []},
        gate={"passed": True},
    )
    return source, row


def _target_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def _selected_at(row: dict) -> datetime:
    return datetime.fromisoformat(row["selected_at"].replace("Z", "+00:00"))


def test_legacy_import_is_atomic_and_idempotent(tmp_path) -> None:
    source, _ = _legacy_source(tmp_path)
    factory = _target_factory()

    first = import_legacy_sqlite(source, factory)
    second = import_legacy_sqlite(source, factory)
    assert first["acceptance_count"] == 1
    assert second["already_imported"] is True
    with factory() as session:
        assert session.scalar(select(func.count(AcceptanceRecordModel.acceptance_id))) == 1
        assert session.scalar(select(func.count(ImportRunModel.import_id))) == 1


def test_invalid_legacy_json_rolls_back_everything(tmp_path) -> None:
    source, _ = _legacy_source(tmp_path)
    with sqlite3.connect(source) as connection:
        connection.execute(
            "UPDATE acceptance_records SET request_json = ?", ("{invalid",)
        )
    factory = _target_factory()

    with pytest.raises(ValueError, match="invalid legacy JSON"):
        import_legacy_sqlite(source, factory)

    with factory() as session:
        assert session.scalar(select(func.count(AcceptanceRecordModel.acceptance_id))) == 0
        assert session.scalar(select(func.count(ImportRunModel.import_id))) == 0


def test_invalid_legacy_timestamp_rolls_back_everything(tmp_path) -> None:
    source, _ = _legacy_source(tmp_path)
    with sqlite3.connect(source) as connection:
        connection.execute(
            "UPDATE acceptance_records SET selected_at = ?", ("not-a-timestamp",)
        )
    factory = _target_factory()

    with pytest.raises(ValueError, match="Invalid isoformat"):
        import_legacy_sqlite(source, factory)

    with factory() as session:
        assert session.scalar(select(func.count(AcceptanceRecordModel.acceptance_id))) == 0
        assert session.scalar(select(func.count(ImportRunModel.import_id))) == 0


def test_equivalent_existing_row_imports_but_hard_conflict_aborts(tmp_path) -> None:
    source, row = _legacy_source(tmp_path)
    equivalent_factory = _target_factory()
    with equivalent_factory() as session, session.begin():
        session.add(
            AcceptanceRecordModel(
                acceptance_id=UUID(row["acceptance_id"]),
                idempotency_key=row["idempotency_key"],
                itinerary_id=row["itinerary_id"],
                trip_id=row["trip_id"],
                selected_at=_selected_at(row),
                schema_version=row["schema_version"],
                data_version=row["data_version"],
                request_payload=row["request"],
                plan_payload=row["plan"],
                gate_payload=row["gate"],
            )
        )
    assert import_legacy_sqlite(source, equivalent_factory)["acceptance_count"] == 1

    conflicting_factory = _target_factory()
    with conflicting_factory() as session, session.begin():
        session.add(
            AcceptanceRecordModel(
                idempotency_key=row["idempotency_key"],
                itinerary_id="different-itinerary",
                trip_id=row["trip_id"],
                selected_at=_selected_at(row),
                schema_version=1,
                data_version=row["data_version"],
                request_payload={},
                plan_payload={},
                gate_payload={},
            )
        )
    with pytest.raises(ValueError, match="conflicting legacy idempotency key"):
        import_legacy_sqlite(source, conflicting_factory)
    with conflicting_factory() as session:
        assert session.scalar(select(func.count(ImportRunModel.import_id))) == 0
