"""The app's two ways to keep a plan in some zones (specs/022-trip-areas/spec.md).

- An AI interpretation names them (`hard_constraints.areas`); the app's confirm step
  sends the proposal as `constraint_overrides`, so they reach that one plan.
- The trip saves them (`preference_overrides.areas`); every plan and replan reads them.
"""

import pytest
from fastapi.testclient import TestClient

from BE.app.main import app
from BE.app.modules.ai_assistance import api
from BE.app.modules.ai_assistance.service import AiAssistanceService
from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.trips.service import TripService
from BE.tests.contract.test_planning_lifecycle_api import lifecycle  # noqa: F401


def _capture(planning) -> list[dict]:
    """Record each planner input without changing what the planner returns."""
    seen: list[dict] = []
    original = planning._planner

    def planner(trip, target, kind):
        seen.append(trip)
        return original(trip, target, kind)

    planning._planner = planner
    return seen


def test_an_area_named_to_the_ai_reaches_the_planner(lifecycle, monkeypatch):  # noqa: F811
    from BE.app.modules.catalog import infrastructure
    planning, owner, _other, trip_id, _url = lifecycle
    monkeypatch.setattr(infrastructure, "load_catalog",
                        lambda: {"snapshot": "fixture-v1", "pois": []})
    ai = AiAssistanceService(planning.settings,
                             completer=lambda *args: {"activities": ["check-in"]})
    app.dependency_overrides[current_principal] = lambda: owner
    monkeypatch.setattr(api, "AiAssistanceService", lambda: ai)
    try:
        response = TestClient(app).post(
            f"/v1/trips/{trip_id}/ai/interpretations",
            json={"text": "ưu tiên check-in trung tâm"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    proposal = response.json()
    assert proposal["hard_constraints"]["areas"] == ["trung_tam"]

    seen = _capture(planning)
    # AiInterpretationProposal.confirmedOverrides in the app: fields + hard + soft.
    result = planning.create_planning_request(
        owner, trip_id, "ai-area-centre-key", target_count=1,
        constraint_overrides={**proposal["fields"], **proposal["hard_constraints"],
                              **proposal["soft_preferences"]},
    )
    assert result["status"] == "completed"
    assert seen[-1]["areas"] == ["trung_tam"]


def test_areas_saved_on_the_trip_reach_every_plan_and_replan(lifecycle, monkeypatch):  # noqa: F811
    planning, owner, _other, trip_id, database_url = lifecycle
    monkeypatch.setenv("DATABASE_URL", database_url)
    trip = TripService().update(
        owner, trip_id, {"preference_overrides": {"areas": ["hoi_an"]}}, 1)
    assert trip["preference_overrides"] == {"areas": ["hoi_an"]}
    seen = _capture(planning)

    planned = planning.create_planning_request(owner, trip_id, "saved-area-plan", target_count=1)
    assert seen[-1]["areas"] == ["hoi_an"]
    # A request that names zones wins for that request only.
    planning.create_planning_request(owner, trip_id, "saved-area-centre", target_count=1,
                                     constraint_overrides={"areas": ["trung_tam"]})
    assert seen[-1]["areas"] == ["trung_tam"]

    accepted = planning.accept(
        owner, planned["alternatives"][0]["alternative_id"], "saved-area-accept")
    planning.replan(owner, trip_id, "saved-area-replan", {
        "source_version_id": accepted["version"]["version_id"], "target_count": 1,
    })
    assert seen[-1]["areas"] == ["hoi_an"]


def test_the_trip_refuses_an_area_label(lifecycle, monkeypatch):  # noqa: F811
    _planning, owner, _other, trip_id, database_url = lifecycle
    monkeypatch.setenv("DATABASE_URL", database_url)
    with pytest.raises(IdentityError) as refused:
        TripService().update(
            owner, trip_id, {"preference_overrides": {"areas": ["Trung tâm"]}}, 1)
    assert (refused.value.code, refused.value.status) == ("VALIDATION_ERROR", 422)
    assert "trung_tam" in refused.value.message
