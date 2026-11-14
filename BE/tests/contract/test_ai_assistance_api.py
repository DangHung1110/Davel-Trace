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
