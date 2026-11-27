"""Focused lifecycle regression coverage; planner algorithms stay in existing suites."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
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
    TripActivityModel,
    TripDayModel,
    TripModel,
)
from BE.app.db.session import clear_engine_cache, get_engine, session_scope
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.planning_lifecycle.service import PlanningLifecycleService
from BE.app.modules.trips.service import TripService

# test_stable_planner_lifecycle runs the real solver on this fixture's settings, so
# the snapshot is pinned to the 750-POI danang-v1 it was written against instead of
# following the app default (danang-v2).
V1_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "snapshots" / "danang-v1"
V2_SNAPSHOT = V1_SNAPSHOT.parent / "danang-v2"
# danang-v2: a summit stop needs the Sun World ticket, the island the Cửa Đại cano.
SUN_WORLD = "ChIJyUQ4aw72QTERCXl5YV-4U1w"
CAU_VANG = "osm:way/683416736"
CU_LAO_CHAM = "manual:cu-lao-cham"
CANO = "fare:cu_lao_cham_boat"


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
        snapshot_dir=str(V1_SNAPSHOT),
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


def test_areas_reach_the_planner_on_a_plan_and_a_replan(lifecycle):
    service, owner, _other, trip_id, database_url = lifecycle
    seen: list[dict] = []

    def planner(trip: dict, target: int, kind: str) -> dict:
        seen.append(trip)
        return _planner(trip, target, kind)

    capturing = PlanningLifecycleService(settings=service.settings, planner=planner)
    capturing.create_planning_request(owner, trip_id, "plain-plan-key", target_count=1)
    planned = capturing.create_planning_request(
        owner, trip_id, "areas-plan-key", target_count=1,
        constraint_overrides={"areas": ["trung_tam", "son_tra_my_khe"]},
    )
    assert seen[0]["areas"] == []
    assert seen[1]["areas"] == ["trung_tam", "son_tra_my_khe"]
    with session_scope(database_url) as session:
        rows = {row.idempotency_key: row
                for row in session.scalars(select(PlanningRequestModel))}
        # No areas: the stored overrides (and the idempotency fingerprint) are unchanged.
        assert "areas" not in rows["plain-plan-key"].input_payload["constraint_overrides"]
        assert rows["areas-plan-key"].input_payload["trip"]["areas"] == [
            "trung_tam", "son_tra_my_khe"]

    accepted = capturing.accept(
        owner, planned["alternatives"][0]["alternative_id"], "areas-accept-key"
    )
    capturing.replan(owner, trip_id, "areas-replan-key", {
        "source_version_id": accepted["version"]["version_id"],
        "changed_constraints": {"areas": ["hoi_an"]},
        "target_count": 1,
    })
    assert seen[2]["areas"] == ["hoi_an"]

    with pytest.raises(ValidationError):
        capturing.create_planning_request(
            owner, trip_id, "unknown-area-key", constraint_overrides={"areas": ["Hội An"]}
        )


# --- replans: the rest of the trip, from now, with what was confirmed before ----------

def _utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc)


def _second_day(database_url: str, trip_id: UUID) -> None:
    """The fixture trip, 10 November, gets an 11 November too."""
    with session_scope(database_url) as session:
        session.get(TripModel, trip_id).end_date = date(2026, 11, 11)
        session.add(TripDayModel(trip_id=trip_id, local_date=date(2026, 11, 11), position=1))


def _finish_first_stop(database_url: str, trip_id: UUID, poi_id: str) -> None:
    with session_scope(database_url) as session:
        day = session.scalar(select(TripDayModel).where(
            TripDayModel.trip_id == trip_id, TripDayModel.position == 0))
        session.add(TripActivityModel(day_id=day.day_id, title="Cà phê", poi_id=poi_id,
                                      progress_state="completed", position=0))


def _capturing(service, clock):
    seen: list[dict] = []

    def planner(trip: dict, target: int, kind: str) -> dict:
        seen.append(trip)
        return _planner(trip, target, kind)

    return PlanningLifecycleService(service.settings, planner=planner, clock=clock), seen


def _accepted(service, owner, trip_id, key, **overrides):
    planned = service.create_planning_request(
        owner, trip_id, f"{key}-plan", target_count=1, constraint_overrides=overrides or None)
    return service.accept(owner, planned["alternatives"][0]["alternative_id"],
                          f"{key}-accept")["version"]["version_id"]


def test_a_replan_plans_the_rest_of_the_trip_from_now(lifecycle):
    service, owner, _other, trip_id, database_url = lifecycle
    _second_day(database_url, trip_id)
    # 07:05 UTC is 14:05 in Đà Nẵng, on the first day of the trip.
    planning, seen = _capturing(service, lambda: _utc(10, 7, 5))
    source = _accepted(planning, owner, trip_id, "rest", base_poi_id="hotel-1")
    _finish_first_stop(database_url, trip_id, "cafe-1")

    replanned = planning.replan(owner, trip_id, "rest-replan", {
        "source_version_id": source, "target_count": 1})

    fresh, replan = seen
    # A fresh plan still covers the whole trip, whatever the time.
    assert (fresh["date"], fresh["days"], fresh["start_time"]) == ("2026-11-10", 2, "07:00")
    assert fresh["resume"] is None
    # The replan: today from now and from the cafe, tomorrow from the hotel at 07:00.
    assert (replan["date"], replan["days"], replan["start_time"]) == ("2026-11-10", 2, "07:00")
    assert replan["origin"]["poi_id"] == "hotel-1"
    assert replan["resume"]["start_time"] == "14:05"
    assert replan["resume"]["origin"]["poi_id"] == "cafe-1"
    assert "cafe-1" in replan["avoid"]
    window = {"day": 1, "date": "2026-11-10", "days": 2, "start_time": "14:05"}
    assert replanned["remaining_context"]["window"] == window
    assert replanned["alternatives"][0]["plan"]["window"] == window


def test_a_replan_on_the_second_day_plans_that_day_alone(lifecycle):
    service, owner, _other, trip_id, database_url = lifecycle
    _second_day(database_url, trip_id)
    planning, seen = _capturing(service, lambda: _utc(11, 2, 15))  # 09:15 on day 2
    source = _accepted(planning, owner, trip_id, "second", base_poi_id="hotel-1")
    _finish_first_stop(database_url, trip_id, "cafe-1")

    planning.replan(owner, trip_id, "second-replan", {"source_version_id": source})

    replan = seen[-1]
    assert (replan["date"], replan["days"], replan["start_time"]) == ("2026-11-11", 1, "09:15")
    assert replan["resume"] is None
    # Yesterday's cafe is behind a night at the hotel.
    assert replan["origin"]["poi_id"] == "hotel-1"


def test_the_device_position_starts_the_replan(lifecycle):
    service, owner, _other, trip_id, database_url = lifecycle
    _second_day(database_url, trip_id)
    planning, seen = _capturing(service, lambda: _utc(10, 7, 5))  # 14:05 on day 1
    source = _accepted(planning, owner, trip_id, "gps", base_poi_id="hotel-1")
    _finish_first_stop(database_url, trip_id, "cafe-1")

    replanned = planning.replan(owner, trip_id, "gps-replan", {
        "source_version_id": source, "target_count": 1,
        "current_location": {"lat": 16.07441234, "lon": 108.24498765, "accuracy_m": 12.4}})

    replan = seen[-1]
    # Today from where the device is (the cafe if the planner cannot use the fix),
    # tomorrow from the hotel.
    first = replan["resume"]["origin"]
    assert (first["lat"], first["lon"], first["accuracy_m"]) == (16.0744, 108.245, 12)
    assert (first["poi_id"], first["fallback_poi_id"]) == (None, "cafe-1")
    assert replan["origin"]["poi_id"] == "hotel-1"
    stored = replanned["remaining_context"]
    assert stored["current_location"] == {"lat": 16.0744, "lon": 108.245, "accuracy_m": 12}
    assert stored["current_location_date"] == "2026-11-10"


def test_a_position_sent_for_tomorrow_is_not_where_tomorrow_starts(lifecycle):
    service, owner, _other, trip_id, database_url = lifecycle
    _second_day(database_url, trip_id)
    planning, seen = _capturing(service, lambda: _utc(10, 10, 30))  # 17:30, day_end 18:00
    source = _accepted(planning, owner, trip_id, "gps-late", base_poi_id="hotel-1")

    planning.replan(owner, trip_id, "gps-late-replan", {
        "source_version_id": source, "current_location": {"lat": 16.0744, "lon": 108.245}})

    replan = seen[-1]
    assert (replan["date"], replan["start_time"]) == ("2026-11-11", "07:00")
    assert replan["origin"]["poi_id"] == "hotel-1"
    assert replan["resume"] is None


def test_a_replan_without_a_position_stores_none(lifecycle):
    service, owner, _other, trip_id, _database_url = lifecycle
    planning, _seen = _capturing(service, lambda: _utc(10, 7, 5))
    source = _accepted(planning, owner, trip_id, "no-gps")

    replanned = planning.replan(owner, trip_id, "no-gps-replan", {"source_version_id": source})

    assert "current_location" not in replanned["remaining_context"]
    assert "current_location_date" not in replanned["remaining_context"]


def test_the_device_time_wins_over_the_server_clock(lifecycle):
    service, owner, _other, trip_id, _database_url = lifecycle
    planning, seen = _capturing(service, lambda: _utc(10, 7, 5))
    source = _accepted(planning, owner, trip_id, "device")

    planning.replan(owner, trip_id, "device-replan", {
        "source_version_id": source, "remaining_from": "2026-11-10T15:30:00+07:00"})

    assert (seen[-1]["date"], seen[-1]["days"], seen[-1]["start_time"]) == (
        "2026-11-10", 1, "15:30")


def test_a_replan_keeps_the_constraints_the_source_was_planned_with(lifecycle):
    service, owner, _other, trip_id, database_url = lifecycle
    planning, seen = _capturing(service, lambda: _utc(10, 1))
    confirmed = {
        "must_visit": ["poi-1"], "avoid": ["poi-9"], "activities": ["biển"],
        "food_preferences": ["hải sản"], "areas": ["son_tra_my_khe"],
        "indicative_budget": 1_500_000.0,
    }
    source = _accepted(planning, owner, trip_id, "kept", **confirmed)

    planning.replan(owner, trip_id, "kept-replan", {"source_version_id": source})
    planning.replan(owner, trip_id, "changed-replan", {
        "source_version_id": source, "changed_constraints": {"areas": ["hoi_an"]}})

    kept, changed = seen[1], seen[2]
    assert kept["must_visit"] == ["poi-1"]
    assert kept["avoid"] == ["poi-9"]
    assert kept["activities"] == ["biển"]
    assert kept["food_prefs"] == ["hải sản"]
    assert kept["areas"] == ["son_tra_my_khe"]
    assert kept["budget"] == 1_500_000
    assert changed["areas"] == ["hoi_an"]
    assert changed["must_visit"] == ["poi-1"]
    with session_scope(database_url) as session:
        rows = {row.idempotency_key: row for row in session.scalars(select(PlanningRequestModel))}
        assert rows["kept-replan"].input_payload["constraint_overrides"] == confirmed
        assert rows["changed-replan"].input_payload["constraint_overrides"] == {
            **confirmed, "areas": ["hoi_an"]}
        assert rows["kept-replan"].remaining_context["changed_constraints"] == {}


def test_nothing_is_left_after_the_last_day(lifecycle):
    service, owner, _other, trip_id, database_url = lifecycle
    planning, _seen = _capturing(service, lambda: _utc(10, 11, 30))  # 18:30, day_end 18:00
    source = _accepted(planning, owner, trip_id, "late")

    with pytest.raises(IdentityError) as closed:
        planning.replan(owner, trip_id, "late-replan", {"source_version_id": source})

    assert (closed.value.code, closed.value.status) == ("REPLAN_WINDOW_CLOSED", 409)
    with session_scope(database_url) as session:
        assert session.scalar(select(func.count()).select_from(PlanningRequestModel).where(
            PlanningRequestModel.request_kind == "replan")) == 0


def test_a_replan_does_not_pay_again_what_the_done_stops_bought(lifecycle):
    """A morning at Cầu Vàng bought the Sun World ticket (good for 3 days), one on Cù
    Lao Chàm the cano (a round trip in the day): the rest of the trip owes no ticket,
    and only the rest of that day owes no cano."""
    service, owner, _other, trip_id, database_url = lifecycle
    _second_day(database_url, trip_id)
    # The planner is the fake one; what is paid is read from danang-v2's own charges.
    v2 = PlanningLifecycleService(service.settings.model_copy(
        update={"snapshot_dir": str(V2_SNAPSHOT)}))
    today, seen = _capturing(v2, lambda: _utc(10, 7, 5))  # 14:05 on the first day
    source = _accepted(today, owner, trip_id, "paid", base_poi_id="hotel-1")
    with session_scope(database_url) as session:
        day = session.scalar(select(TripDayModel).where(
            TripDayModel.trip_id == trip_id, TripDayModel.position == 0))
        for position, poi_id in enumerate((CAU_VANG, CU_LAO_CHAM)):
            session.add(TripActivityModel(day_id=day.day_id, title=poi_id, poi_id=poi_id,
                                          progress_state="completed", position=position))

    today.replan(owner, trip_id, "paid-today", {"source_version_id": source})
    tomorrow, later = _capturing(v2, lambda: _utc(11, 2, 15))  # 09:15 on the second day
    tomorrow.replan(owner, trip_id, "paid-tomorrow", {"source_version_id": source})

    fresh, same_day, next_day = seen[0], seen[-1], later[-1]
    assert fresh["paid_access"] == []
    assert SUN_WORLD in same_day["paid_access"] and CANO not in same_day["paid_access"]
    assert same_day["resume"]["paid_access"] == [CANO]
    assert SUN_WORLD in next_day["paid_access"] and CANO not in next_day["paid_access"]
    assert next_day["resume"] is None
    with session_scope(database_url) as session:
        # Read from the trip, not sent: neither stored nor in the fingerprint.
        row = session.scalar(select(PlanningRequestModel).where(
            PlanningRequestModel.idempotency_key == "paid-today"))
        assert "paid_access" not in json.dumps(row.remaining_context)


def test_a_retried_replan_gets_the_plan_it_asked_for(lifecycle):
    service, owner, _other, trip_id, _database_url = lifecycle
    planning, _seen = _capturing(service, lambda: _utc(10, 7, 5))
    source = _accepted(planning, owner, trip_id, "retry")
    first = planning.replan(owner, trip_id, "retry-replan", {"source_version_id": source})

    # The same key later, even once the day is over: the clock is not what was sent.
    later, _ = _capturing(service, lambda: _utc(10, 11, 30))
    again = later.replan(owner, trip_id, "retry-replan", {"source_version_id": source})

    assert again["request_id"] == first["request_id"]
    assert again["remaining_context"]["window"]["start_time"] == "14:05"
