"""Focused lifecycle regression coverage; planner algorithms stay in existing suites."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select

from BE.app.core.config import AppMode, Settings
from BE.app.db.base import Base
from BE.app.db.models import (
    AcceptanceRecordModel,
    AccountModel,
    ItineraryAlternativeModel,
    ActiveItineraryVersionModel,
    ItineraryVersionModel,
    ItineraryVersionTransitionModel,
    PlanningRequestModel,
    TravelerProfileModel,
    TripDayModel,
    TripModel,
)
from BE.app.db.session import clear_engine_cache, get_engine, session_scope
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.planning_lifecycle.service import PlanningLifecycleService
from BE.app.modules.trips.service import TripService


def _planner(_trip: dict, target: int, _kind: str) -> dict:
    plans = []
    for rank in range(1, min(target, 2) + 1):
        plans.append({
            "itinerary_id": f"legacy-{rank}",
            "profile": "balanced" if rank == 1 else "savings",
            "activities": [{
                "poi_id": f"poi-{rank}", "start": "09:00", "end": "10:00"
            }],
            "total_cost": rank * 100_000,
            "total_km": float(rank),
            "total_min": 60,
            "deterministic_rank": rank,
            "deterministic_score": 1.0 / rank,
            "gate": {
                "passed": True,
                "families": {
                    "entity": {"passed": True},
                    "temporal": {"passed": True},
                    "financial": {"passed": True},
                    "movement": {"passed": True},
                    "traveler_constraint": {"passed": True},
                },
            },
            "data_version": "danang-test-v1",
        })
    return {
        "plans": plans,
        "solution_pool": {
            "target": target,
            "returned": len(plans),
            "shortage_reason": (
                "insufficient_feasible_supply" if len(plans) < target else None
            ),
        },
    }


@pytest.fixture()
def lifecycle(tmp_path: Path):
    clear_engine_cache()
    database_url = f"sqlite+pysqlite:///{tmp_path / 'lifecycle.db'}"
    settings = Settings(
        app_mode=AppMode.test,
        database_url=database_url,
        snapshot_name="danang-test-v1",
    )
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    owner_id, other_id = uuid4(), uuid4()
    with session_scope(database_url) as session:
        for account_id, email in (
            (owner_id, "owner@example.test"),
            (other_id, "other@example.test"),
        ):
            session.add(AccountModel(
                account_id=account_id,
                email_normalized=email,
                password_hash="test-only",
                status="active",
            ))
            session.add(TravelerProfileModel(
                account_id=account_id,
                display_name=email,
            ))
        session.flush()
        trip = TripModel(
            account_id=owner_id,
            title="Đà Nẵng",
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 10),
            traveler_count=2,
            indicative_budget=2_000_000,
            preferred_transport="motorbike",
            day_start=time(7),
            day_end=time(18),
            profile_version=1,
            profile_snapshot={
                "party_type": "friends",
                "trip_purpose": "leisure",
                "pace": 2,
                "fitness": 2,
                "spending_style": "balanced",
            },
        )
        session.add(trip)
        session.flush()
        session.add(TripDayModel(
            trip_id=trip.trip_id,
            local_date=trip.start_date,
            position=0,
        ))
        session.flush()
        trip_id = trip.trip_id
    service = PlanningLifecycleService(settings=settings, planner=_planner)
    owner = Principal(owner_id, uuid4(), frozenset({"traveler"}), "test-owner")
    other = Principal(other_id, uuid4(), frozenset({"traveler"}), "test-other")
    yield service, owner, other, trip_id, database_url
    engine.dispose()
    clear_engine_cache()


def test_plan_accept_history_reactivate_and_replan_are_durable_and_idempotent(
    lifecycle,
):
    service, owner, _other, trip_id, database_url = lifecycle
    planned = service.create_planning_request(
        owner, trip_id, "plan-stable-key", target_count=5
    )
    replay = service.create_planning_request(
        owner, trip_id, "plan-stable-key", target_count=5
    )

    assert planned == replay
    assert planned["status"] == "completed"
    assert planned["returned_count"] == 2
    assert planned["shortage_reason"] == "insufficient_feasible_supply"
    assert all(item["gate"]["passed"] for item in planned["alternatives"])

    alternative_id = planned["alternatives"][0]["alternative_id"]
    accepted = service.accept(owner, alternative_id, "accept-stable-key")
    accepted_replay = service.accept(owner, alternative_id, "accept-stable-key")
    assert accepted == accepted_replay
    assert accepted["version"]["active"] is True

    history = service.list_versions(owner, trip_id)
    assert history["active_version_id"] == accepted["version"]["version_id"]
    assert len(history["items"]) == 1

    replanned = service.replan(owner, trip_id, "replan-stable-key", {
        "source_version_id": accepted["version"]["version_id"],
        "target_count": 2,
    })
    child = service.accept(
        owner,
        replanned["alternatives"][0]["alternative_id"],
        "replan-accept-key",
    )
    assert child["version"]["parent_version_id"] == accepted["version"]["version_id"]

    reactivated = service.activate(
        owner, accepted["version"]["version_id"], "reactivate-stable-key"
    )
    assert reactivated["version"]["active"] is True
    assert reactivated["transition"]["reason"] == "reactivate"

    with session_scope(database_url) as session:
        assert session.scalar(select(func.count()).select_from(PlanningRequestModel)) == 2
        assert session.scalar(select(func.count()).select_from(ItineraryAlternativeModel)) == 4
        assert session.scalar(select(func.count()).select_from(ItineraryVersionModel)) == 2
        assert session.scalar(select(func.count()).select_from(AcceptanceRecordModel)) == 2
        assert session.scalar(select(func.count()).select_from(ItineraryVersionTransitionModel)) == 3

    clear_engine_cache()
    restarted = PlanningLifecycleService(settings=service.settings, planner=_planner)
    durable = restarted.get_version(owner, child["version"]["version_id"])
    assert durable["parent_version_id"] == accepted["version"]["version_id"]


def test_foreign_resources_are_not_disclosed_and_retry_conflicts_are_rejected(
    lifecycle,
):
    service, owner, other, trip_id, _database_url = lifecycle
    planned = service.create_planning_request(
        owner, trip_id, "private-plan-key", target_count=1
    )
    request_id = planned["request_id"]
    alternative_id = planned["alternatives"][0]["alternative_id"]

    with pytest.raises(IdentityError) as hidden_request:
        service.get_request(other, request_id)
    with pytest.raises(IdentityError) as hidden_alternative:
        service.accept(other, alternative_id, "foreign-accept-key")
    assert hidden_request.value.status == 404
    assert hidden_alternative.value.status == 404

    with pytest.raises(IdentityError) as conflict:
        service.create_planning_request(
            owner, trip_id, "private-plan-key", target_count=2
        )
    assert conflict.value.code == "IDEMPOTENCY_CONFLICT"


def test_trip_mutation_preserves_active_version_and_invalidates_open_alternatives(
    lifecycle, monkeypatch,
):
    service, owner, _other, trip_id, database_url = lifecycle
    monkeypatch.setenv("DATABASE_URL", database_url)
    initial = service.create_planning_request(
        owner, trip_id, "initial-plan-key", target_count=1
    )
    accepted = service.accept(
        owner, initial["alternatives"][0]["alternative_id"], "initial-accept-key"
    )
    pending = service.create_planning_request(
        owner, trip_id, "pending-plan-key", target_count=1
    )

    TripService().update(owner, trip_id, {"title": "Đà Nẵng đã đổi"}, 1)

    with session_scope(database_url) as session:
        trip = session.get(TripModel, trip_id)
        active = session.get(ActiveItineraryVersionModel, trip_id)
        alternative = session.get(
            ItineraryAlternativeModel,
            UUID(pending["alternatives"][0]["alternative_id"]),
        )
        assert trip.review_state == "needs_review"
        assert str(active.version_id) == accepted["version"]["version_id"]
        assert alternative.selectability_state == "invalidated"

    with pytest.raises(IdentityError) as stale:
        service.accept(
            owner,
            pending["alternatives"][0]["alternative_id"],
            "pending-accept-key",
        )
    assert stale.value.code == "ALTERNATIVE_STALE"
