from __future__ import annotations

from fastapi.testclient import TestClient

from BE.app.main import app


def test_valid_correlation_id_is_echoed_on_success() -> None:
    response = TestClient(app).get(
        "/v1/health", headers={"X-Correlation-ID": "mobile-action-1234"}
    )
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "mobile-action-1234"
    assert response.json()["correlation_id"] == "mobile-action-1234"


def test_invalid_correlation_id_is_replaced_on_error() -> None:
    response = TestClient(app).post(
        "/v1/itinerary/select",
        json={},
        headers={"X-Correlation-ID": "bad id with spaces"},
    )
    assert response.status_code == 422
    replacement = response.headers["X-Correlation-ID"]
    assert replacement != "bad id with spaces"
    assert len(replacement) >= 8
    assert response.json()["error"] == "VALIDATION_ERROR"
