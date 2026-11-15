"""Real stable solver through the durable product adapter, isolated test DB."""

from BE.app.modules.planning_lifecycle.service import PlanningLifecycleService
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
        return itinerary.itinerary(itinerary.ItineraryIn(
            trip=TripRequest(**trip), profiles=["balanced"]
        ))
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
