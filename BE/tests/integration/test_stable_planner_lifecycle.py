"""Real stable solver through the durable product adapter, isolated test DB."""

from BE.app.modules.planning_lifecycle.service import PlanningLifecycleService
from BE.app.modules.planning_lifecycle.stable_planner import with_product_evidence
from BE.app.routers import itinerary
from BE.app.schemas.trip import TripRequest
from BE.app.services import trip_ctx
from BE.tests.contract.test_planning_lifecycle_api import lifecycle


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


def test_a_real_replan_starts_at_the_device_position(lifecycle, monkeypatch):
    """The device position reaches the solver and the product gate (specs/024)."""
    from datetime import datetime, timezone

    fixture_service, owner, _other, trip_id, _url = lifecycle
    monkeypatch.setattr(itinerary, "get_settings", lambda: fixture_service.settings)
    monkeypatch.setattr(
        trip_ctx.weather_svc, "fetch_forecast",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline test")),
    )

    def calculate(trip, target, kind):
        return with_product_evidence(itinerary.itinerary(itinerary.ItineraryIn(
            trip=TripRequest(**trip), profiles=["balanced"]
        )), fixture_service.settings.snapshot_name)

    # 07:05 UTC is 14:05 in Da Nang, on the day of the fixture trip.
    service = PlanningLifecycleService(
        fixture_service.settings, planner=calculate,
        clock=lambda: datetime(2026, 11, 10, 7, 5, tzinfo=timezone.utc))
    planned = service.create_planning_request(owner, trip_id, "gps-real-plan", target_count=1)
    version = service.accept(owner, planned["alternatives"][0]["alternative_id"],
                             "gps-real-accept")["version"]["version_id"]
    # A fix by the Dragon Bridge, 10 m accurate.
    replanned = service.replan(owner, trip_id, "gps-real-replan", {
        "source_version_id": version, "target_count": 1,
        "current_location": {"lat": 16.0612, "lon": 108.2270, "accuracy_m": 10}})

    assert replanned["returned_count"] == 1
    alternative = replanned["alternatives"][0]
    plan = alternative["plan"]
    assert plan["gps_origin"]["used"] is True
    assert plan["segments"][0]["from_id"] == plan["gps_origin"]["origin_id"]
    assert plan["segments"][0]["source"] == "gps_estimate"
    first_leg = plan["segments"][0]["minutes"]
    start = plan["activities"][0]["start"]
    assert int(start[:2]) * 60 + int(start[3:5]) >= 14 * 60 + 5 + first_leg
    assert all(family["passed"] for family in alternative["gate"]["families"].values())
