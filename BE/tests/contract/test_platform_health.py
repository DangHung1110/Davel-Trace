from __future__ import annotations

from fastapi.testclient import TestClient

from BE.app.main import app


client = TestClient(app)


def test_health_preserves_existing_fields_and_adds_correlation() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["snapshot"]
    assert response.headers["X-Correlation-ID"]
    assert response.json()["correlation_id"] == response.headers["X-Correlation-ID"]


def test_ready_reports_required_and_optional_components() -> None:
    response = client.get("/v1/ready")
    assert response.status_code in {200, 503}
    body = response.json()
    assert body["status"] in {"ready", "not_ready"}
    components = {item["name"]: item for item in body["components"]}
    assert {"database", "schema", "catalog", "osrm", "ai"} <= components.keys()
    assert components["osrm"]["required"] is False
    assert components["ai"]["required"] is False
