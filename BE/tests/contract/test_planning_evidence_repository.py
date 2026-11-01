from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from BE.app.db.base import Base
from BE.app.modules.planning_evidence.infrastructure import (
    create_postgres_planning_evidence_service,
)


def _service(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'evidence.db'}")
    Base.metadata.create_all(engine)
    return create_postgres_planning_evidence_service(
        sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    )


def test_acceptance_is_idempotent_and_survives_three_reconnections(tmp_path) -> None:
    service = _service(tmp_path)
    payload = {
        "idempotency_key": "contract-key-001",
        "itinerary_id": "it-1",
        "trip_id": "trip-1",
        "data_version": "danang-v1",
        "request": {"budget": 1000000},
        "plan": {"activities": []},
        "gate": {"passed": True},
    }
    first = service.save_acceptance(**payload)
    second = service.save_acceptance(**payload)
    assert first["acceptance_id"] == second["acceptance_id"]
    for _ in range(3):
        assert service.get_acceptance(first["acceptance_id"])["trip_id"] == "trip-1"
    assert service.count_acceptances() == 1


def test_shadow_round_trip_and_stable_ordering(tmp_path) -> None:
    service = _service(tmp_path)
    saved = service.save_shadow(
        {
            "trip_id": "trip-1",
            "data_version": "danang-v1",
            "candidate_ids": ["a", "b"],
            "forward": {"winner": "a"},
            "reverse": {"winner": "a"},
            "consensus": {"winner": "a"},
            "deterministic_top_id": "a",
            "shadow_top_id": "a",
            "swap_consistent": True,
            "veto_count": 0,
            "status": "completed",
        }
    )
    rows = service.list_shadows(limit=10)
    assert rows[0]["observation_id"] == saved["observation_id"]
    assert rows[0]["swap_consistent"] is True


def test_acceptance_ordering_and_failed_write_rolls_back(tmp_path) -> None:
    service = _service(tmp_path)
    now = datetime.now(timezone.utc)
    common = {
        "trip_id": "trip-order",
        "data_version": "danang-v1",
        "request": {},
        "plan": {"activities": []},
        "gate": {"passed": True},
    }
    service.save_acceptance(
        **common,
        idempotency_key="order-key-older",
        itinerary_id="it-old",
        selected_at=now - timedelta(minutes=1),
    )
    service.save_acceptance(
        **common,
        idempotency_key="order-key-newer",
        itinerary_id="it-new",
        selected_at=now,
    )
    assert [row["itinerary_id"] for row in service.list_acceptances("trip-order")] == [
        "it-new",
        "it-old",
    ]
    before = service.count_acceptances()
    with pytest.raises(IntegrityError):
        service.save_acceptance(
            **common,
            idempotency_key="rollback-key-001",
            itinerary_id="it-invalid",
            deterministic_rank=0,
        )
    assert service.count_acceptances() == before


def test_shadow_survives_three_repository_reconnections(tmp_path) -> None:
    first = _service(tmp_path)
    saved = first.save_shadow(
        {
            "trip_id": "trip-reconnect",
            "data_version": "danang-v1",
            "candidate_ids": ["a", "b"],
            "forward": {},
            "reverse": {},
            "consensus": {},
            "swap_consistent": False,
            "veto_count": 0,
            "status": "completed",
        }
    )
    for _ in range(3):
        reconnected = _service(tmp_path)
        rows = reconnected.list_shadows(limit=10)
        assert any(
            row["observation_id"] == saved["observation_id"] for row in rows
        )
