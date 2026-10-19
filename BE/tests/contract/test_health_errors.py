def test_health_reports_database_and_snapshot(client):
    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ready",
        "snapshot": "danang-v1",
    }


def test_validation_uses_structured_error_envelope(client):
    response = client.post("/v1/profiles", json={"display_name": "   "})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"]
    assert isinstance(payload["error"]["details"], dict)
