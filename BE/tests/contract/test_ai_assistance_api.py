"""Ownership and failure isolation for the product AI boundary."""

import pytest
from fastapi.testclient import TestClient

from BE.app.main import app
from BE.app.modules.ai_assistance import api
from BE.app.modules.ai_assistance.service import AiAssistanceService
from BE.app.modules.identity.dependencies import current_principal
from BE.app.services.llm import LLMError
from BE.tests.contract.test_planning_lifecycle_api import lifecycle


def test_interpretation_requires_authentication():
    response = TestClient(app).post(
        "/v1/trips/00000000-0000-0000-0000-000000000001/ai/interpretations",
        json={"text": "đi biển"},
    )
    assert response.status_code == 401


def test_foreign_trip_is_rejected_before_external_call(lifecycle, monkeypatch):
    planning, _owner, other, trip_id, _url = lifecycle
    calls = []
    ai = AiAssistanceService(
        planning.settings, completer=lambda *args: calls.append(args)
    )
    app.dependency_overrides[current_principal] = lambda: other
    monkeypatch.setattr(api, "AiAssistanceService", lambda: ai)
    try:
        response = TestClient(app).post(
            f"/v1/trips/{trip_id}/ai/interpretations", json={"text": "đi biển"}
        )
        assert response.status_code == 404
        assert calls == []
    finally:
        app.dependency_overrides.clear()


def test_owned_interpretation_resolves_locally_and_only_confirmed_ids_reach_planner(
    lifecycle, monkeypatch,
):
    from BE.app.modules.catalog import infrastructure
    planning, owner, _other, trip_id, _url = lifecycle
    calls = []
    def complete(prompt, schema, settings):
        calls.append(prompt)
        assert "KNOWN_POI_NAMES" not in prompt
        assert "Cà phê An chi nhánh" not in prompt
        return {"travelers": 2, "budget": 3_000_000,
                "must_visit": ["cau rong", "ca phe an"], "avoid": ["quan binh"]}
    catalog = {"snapshot": "fixture-v1", "pois": [
        {"poi_id": "bridge", "name": "Cầu Rồng", "verified": True},
        {"poi_id": "an-1", "name": "Cà phê An chi nhánh 1", "verified": True, "lat": 16.1, "lon": 108.1},
        {"poi_id": "an-2", "name": "Cà phê An chi nhánh 2", "verified": True, "lat": 16.2, "lon": 108.2},
        {"poi_id": "binh-1", "name": "Quán Bình 1", "verified": True},
        {"poi_id": "binh-2", "name": "Quán Bình 2", "verified": True},
    ]}
    monkeypatch.setattr(infrastructure, "load_catalog", lambda: catalog)
    ai = AiAssistanceService(planning.settings, completer=complete)
    app.dependency_overrides[current_principal] = lambda: owner
    monkeypatch.setattr(api, "AiAssistanceService", lambda: ai)
    try:
        response = TestClient(app).post(
            f"/v1/trips/{trip_id}/ai/interpretations",
            json={"text": "Đi 2 người, 3 triệu, ghé cau rong, ca phe an, tránh quan binh"},
        )
        assert response.status_code == 200
        proposal = response.json()
        assert proposal["status"] == "review_required"
        assert proposal["hard_constraints"]["must_visit"] == ["bridge"]
        assert [item["constraint"] for item in proposal["place_resolutions"]] == ["must_visit", "avoid"]
        assert len(calls) == 1
        assert planning.list_versions(owner, trip_id)["items"] == []
        captured = []
        original_planner = planning._planner
        def planner(trip, target, kind):
            captured.append(trip)
            return original_planner(trip, target, kind)
        planning._planner = planner
        result = planning.create_planning_request(
            owner, trip_id, "confirmed-local-places", target_count=1,
            constraint_overrides={**proposal["fields"],
                **proposal["hard_constraints"], **proposal["soft_preferences"],
                "must_visit": ["bridge", "an-2"], "avoid": ["binh-1"]},
        )
        assert result["status"] == "completed"
        assert captured[0]["must_visit"] == ["bridge", "an-2"]
        assert captured[0]["avoid"] == ["binh-1"]
        assert len(calls) == 1  # planning itself never calls AI
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("reason", ["disabled", "auth", "quota", "timeout", "schema"])
def test_normalized_ai_failure_keeps_structured_planning_usable(
    lifecycle, monkeypatch, reason
):
    planning, owner, _other, trip_id, _url = lifecycle
    def fail(*args):
        raise LLMError(reason, "secret-provider-body")
    ai = AiAssistanceService(planning.settings, completer=fail)
    app.dependency_overrides[current_principal] = lambda: owner
    monkeypatch.setattr(api, "AiAssistanceService", lambda: ai)
    try:
        response = TestClient(app).post(
            f"/v1/trips/{trip_id}/ai/interpretations", json={"text": "đi biển"}
        )
        assert response.status_code == 503
        assert response.json()["error"] == f"LLM_{reason.upper()}"
        if reason == "quota":
            assert "giới hạn" in response.json()["message"]
        if reason == "auth":
            assert "API key" in response.json()["message"]
        assert "secret-provider-body" not in response.text
        result = planning.create_planning_request(
            owner, trip_id, f"after-ai-{reason}-key", target_count=1
        )
        assert result["status"] == "completed"
        assert result["returned_count"] == 1
    finally:
        app.dependency_overrides.clear()


def test_owned_explanation_falls_back_and_shadow_is_non_authoritative(lifecycle):
    planning, owner, other, trip_id, _url = lifecycle
    request = planning.create_planning_request(
        owner, trip_id, "ai-explanation-plan", target_count=2
    )
    alternative_id = request["alternatives"][0]["alternative_id"]
    ai = AiAssistanceService(planning.settings)
    explanation = ai.explain_owned(owner, alternative_id)
    assert explanation["source"] == "deterministic"
    shadow = ai.shadow_owned(owner, request["request_id"])
    assert shadow["authoritative"] is False
    assert shadow["status"] == "skipped"
    assert planning.get_request(owner, request["request_id"]) == request


def test_enabled_shadow_checks_both_orders_without_reordering(lifecycle):
    import json
    from BE.app.modules.ai_assistance.domain import ShadowDraft
    planning, owner, _other, trip_id, _url = lifecycle
    request = planning.create_planning_request(
        owner, trip_id, "enabled-shadow-plan-key", target_count=2
    )
    ids = [item["alternative_id"] for item in request["alternatives"]]
    seen = []
    def complete(prompt, schema, settings):
        assert schema is ShadowDraft
        candidates = json.loads(prompt.split("\n", 1)[1])
        seen.append([item["id"] for item in candidates])
        return {"ranked_ids": list(reversed(ids))}
    settings = planning.settings.model_copy(update={
        "llm_provider": "local", "llm_shadow_enabled": True,
    })
    ai = AiAssistanceService(settings, completer=complete)
    result = ai.shadow_owned(owner, request["request_id"])
    assert seen == [ids, list(reversed(ids))]
    assert result["swap_consistent"] is True
    assert result["shadow_top_id"] == ids[-1]
    assert planning.get_request(owner, request["request_id"]) == request
