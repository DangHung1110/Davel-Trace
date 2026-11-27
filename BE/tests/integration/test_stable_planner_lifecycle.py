"""Real stable solver through the durable product adapter, isolated test DB."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from BE.app.db.models import ExpenseEntryModel, TripActivityModel, TripDayModel
from BE.app.db.session import session_scope
from BE.app.modules.planning_lifecycle.service import PlanningLifecycleService
from BE.app.modules.planning_lifecycle.stable_planner import with_product_evidence
from BE.app.routers import itinerary
from BE.app.schemas.trip import TripRequest
from BE.app.services import trip_ctx
from BE.tests.contract.test_planning_lifecycle_api import (
    CAU_VANG, V2_SNAPSHOT, _planner, lifecycle)

FANTASY_PARK = "osm:node/10154412164"


def test_real_plan_accept_restart_preserves_recorded_evidence(lifecycle, monkeypatch):
    fixture_service, owner, _other, trip_id, _url = lifecycle
    monkeypatch.setattr(itinerary, "get_settings", lambda: fixture_service.settings)
    monkeypatch.setattr(
        trip_ctx.weather_svc, "fetch_forecast",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline test")),
    )
    def calculate(trip, target, kind):
        # The product adapter: the stable planner, then the product boundary.
        return with_product_evidence(itinerary.itinerary(itinerary.ItineraryIn(
            trip=TripRequest(**trip), profiles=["balanced"]
        )), fixture_service.settings.snapshot_name)
    service = PlanningLifecycleService(fixture_service.settings, planner=calculate)
    planned = service.create_planning_request(
        owner, trip_id, "real-stable-lifecycle-key", target_count=1
    )
    assert planned["returned_count"] == 1
    alternative = planned["alternatives"][0]
    assert len(alternative["gate"]["families"]) == 5
    assert alternative["plan"]["planner_source"] == "35872c2"
    accepted = service.accept(owner, alternative["alternative_id"], "real-stable-accept-key")
    restarted = PlanningLifecycleService(fixture_service.settings)
    restored = restarted.get_version(owner, accepted["version"]["version_id"])
    assert restored["plan"] == accepted["version"]["plan"]
    assert restored["gate"] == accepted["version"]["gate"]
    assert restored["data_version"] == accepted["version"]["data_version"]


def test_a_real_replan_does_not_buy_the_sun_world_ticket_twice(lifecycle, monkeypatch):
    """Cầu Vàng is done and its Sun World ticket (850,000 x 2) is logged: 800,000 of
    2,500,000 is left, and Fantasy Park, still a must, sits behind the same ticket.
    Charged a second ticket the rest of the day had no plan; paid, it fits."""
    fixture_service, owner, _other, trip_id, database_url = lifecycle
    settings = fixture_service.settings.model_copy(update={"snapshot_dir": str(V2_SNAPSHOT)})
    monkeypatch.setattr(itinerary, "get_settings", lambda: settings)
    monkeypatch.setattr(
        trip_ctx.weather_svc, "fetch_forecast",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline test")),
    )
    clock = lambda: datetime(2026, 11, 10, 3, 30, tzinfo=timezone.utc)  # 10:30 in Đà Nẵng
    must = [CAU_VANG, FANTASY_PARK]

    def source_plan(trip, target, kind):
        # The version the morning followed; only the replan below runs the solver.
        planned = _planner(trip, 1, kind)
        planned["plans"][0]["activities"] = [
            {"poi_id": poi_id, "start": "09:00", "end": "10:00"} for poi_id in must]
        return planned

    sourcing = PlanningLifecycleService(settings, planner=source_plan, clock=clock)
    planned = sourcing.create_planning_request(
        owner, trip_id, "bana-plan-key", target_count=1,
        constraint_overrides={"must_visit": must, "indicative_budget": 2_500_000})
    source = sourcing.accept(owner, planned["alternatives"][0]["alternative_id"],
                             "bana-accept-key")["version"]["version_id"]
    with session_scope(database_url) as session:
        day = session.scalar(select(TripDayModel).where(TripDayModel.trip_id == trip_id))
        done = TripActivityModel(day_id=day.day_id, title="Cầu Vàng", poi_id=CAU_VANG,
                                 progress_state="completed", position=0)
        session.add(done)
        session.flush()
        session.add(ExpenseEntryModel(
            trip_id=trip_id, day_id=day.day_id, activity_id=done.activity_id,
            label="Vé Sun World x2", amount=Decimal("1700000"), category="ticket",
            spent_at=clock(), created_by=owner.account_id))

    replanned = PlanningLifecycleService(settings, clock=clock).replan(
        owner, trip_id, "bana-replan-key", {"source_version_id": source, "target_count": 1})

    assert replanned["returned_count"] == 1
    plan = replanned["alternatives"][0]["plan"]
    assert FANTASY_PARK in {activity["poi_id"] for activity in plan["activities"]}
    assert not plan.get("access_fees")
    assert plan["total_cost"] <= 800_000
