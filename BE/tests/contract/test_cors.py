from __future__ import annotations

from fastapi.testclient import TestClient

from BE.app.main import app


client = TestClient(app)


def test_configured_local_origin_is_allowed() -> None:
    response = client.options(
        "/v1/health",
        headers={
            "Origin": "http://127.0.0.1:5501",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5501"


def test_unlisted_origin_is_not_allowed() -> None:
    response = client.options(
        "/v1/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None
