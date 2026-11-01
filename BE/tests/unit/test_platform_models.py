from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from BE.app.db.base import Base
from BE.app.db.models import (
    AcceptanceRecordModel,
    ImportRunModel,
    SeedRunModel,
    ShadowObservationModel,
)


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_acceptance_idempotency_and_length_constraints() -> None:
    engine = _engine()
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add(
            AcceptanceRecordModel(
                idempotency_key="valid-key-001",
                itinerary_id="it-1",
                trip_id="trip-1",
                selected_at=now,
                schema_version=1,
                data_version="danang-v1",
                request_payload={},
                plan_payload={},
                gate_payload={},
            )
        )
        session.commit()
        session.add(
            AcceptanceRecordModel(
                idempotency_key="valid-key-001",
                itinerary_id="it-2",
                trip_id="trip-1",
                selected_at=now,
                schema_version=1,
                data_version="danang-v1",
                request_payload={},
                plan_payload={},
                gate_payload={},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_seed_mode_rejects_production() -> None:
    engine = _engine()
    with Session(engine) as session:
        session.add(
            SeedRunModel(
                dataset_name="demo",
                dataset_version="1",
                checksum="a" * 64,
                mode="production",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    ("overrides", "expected_constraint"),
    [
        ({"idempotency_key": "short"}, "idempotency_key_length"),
        ({"schema_version": 0}, "schema_version_positive"),
        ({"deterministic_rank": 0}, "deterministic_rank_positive"),
    ],
)
def test_acceptance_check_constraints(overrides, expected_constraint) -> None:
    engine = _engine()
    values = {
        "idempotency_key": "valid-key-constraint",
        "itinerary_id": "it-1",
        "trip_id": "trip-1",
        "selected_at": datetime.now(timezone.utc),
        "schema_version": 1,
        "data_version": "danang-v1",
        "request_payload": {},
        "plan_payload": {},
        "gate_payload": {},
        "deterministic_rank": 1,
        **overrides,
    }
    with Session(engine) as session:
        session.add(AcceptanceRecordModel(**values))
        with pytest.raises(IntegrityError) as exc:
            session.commit()
    assert expected_constraint in str(exc.value)


@pytest.mark.parametrize(
    ("overrides", "expected_constraint"),
    [
        ({"length_correlation": 1.1}, "correlation_range"),
        ({"veto_count": -1}, "veto_count_non_negative"),
        ({"latency_ms": -1}, "latency_non_negative"),
        ({"status": "unknown"}, "status_valid"),
    ],
)
def test_shadow_check_constraints(overrides, expected_constraint) -> None:
    engine = _engine()
    values = {
        "trip_id": "trip-1",
        "created_at": datetime.now(timezone.utc),
        "data_version": "danang-v1",
        "candidate_ids": [],
        "forward_result": {},
        "reverse_result": {},
        "consensus_result": {},
        "swap_consistent": False,
        "length_correlation": 0.0,
        "veto_count": 0,
        "status": "completed",
        "latency_ms": 0,
        **overrides,
    }
    with Session(engine) as session:
        session.add(ShadowObservationModel(**values))
        with pytest.raises(IntegrityError) as exc:
            session.commit()
    assert expected_constraint in str(exc.value)


@pytest.mark.parametrize("field", ["acceptance_count", "shadow_count"])
def test_import_counts_cannot_be_negative(field: str) -> None:
    engine = _engine()
    values = {
        "source_kind": "acceptance-sqlite-v1",
        "source_fingerprint": "a" * 64,
        "status": "completed",
        "acceptance_count": 0,
        "shadow_count": 0,
        field: -1,
    }
    with Session(engine) as session:
        session.add(ImportRunModel(**values))
        with pytest.raises(IntegrityError) as exc:
            session.commit()
    assert f"{field}_non_negative" in str(exc.value)
