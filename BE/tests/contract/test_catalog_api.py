from pathlib import Path

import pytest

from BE.app.main import app
from BE.tests.support.asgi_client import request

V2_SNAPSHOT = Path("BE/data/snapshots/danang-v2")


def test_public_catalog_search_and_detail_preserve_snapshot_provenance():
    original = app.state.catalog_reader
    app.state.catalog_reader = lambda: {"snapshot": "fixture-v1", "pois": [{
        "poi_id": "manual:test-place", "name": "Cầu Rồng", "type": "landmark",
        "cat": "landmark", "lat": 16.06, "lon": 108.22, "verified": False,
        "source": "fixture-source", "fetched_at": "2026-10-03",
    }]}
    try:
        response = request(app, "GET", "/v1/pois", params={"q": "cau rong", "limit": 10})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["snapshot_version"] == "fixture-v1"
        assert payload["items"][0]["poi_id"] == "manual:test-place"
        assert payload["items"][0]["verified"] is False
        detail = request(app, "GET", "/v1/pois/manual:test-place")
        assert detail.status_code == 200
        assert detail.json()["source"] == "fixture-source"
        assert detail.json()["opening_hours_state"] == "unknown"
    finally:
        app.state.catalog_reader = original


def test_public_catalog_reports_unknown_place_and_version():
    original = app.state.catalog_reader
    app.state.catalog_reader = lambda: {"snapshot": "fixture-v1", "pois": [{
        "poi_id": "p", "name": "Place", "type": "landmark", "cat": "landmark",
        "lat": 16.0, "lon": 108.0, "verified": True,
    }]}
    try:
        assert request(app, "GET", "/v1/pois/missing").status_code == 404
        assert request(app, "GET", "/v1/pois", params={"version": "old-v0"}).status_code == 404
    finally:
        app.state.catalog_reader = original


@pytest.mark.skipif(not (V2_SNAPSHOT / "pois.json").is_file(), reason="danang-v2 snapshot missing")
def test_catalog_answers_on_the_v21_snapshot(monkeypatch):
    """SNAPSHOT_DIR=danang-v2 used to answer 503: v2.1 rows carry no `verified`."""
    monkeypatch.setenv("SNAPSHOT_DIR", str(V2_SNAPSHOT))
    monkeypatch.setenv("SNAPSHOT_NAME", "danang-v2")
    response = request(app, "GET", "/v1/pois",
                       params={"q": "my khe", "category": "beach", "limit": 10})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["snapshot_version"] == "danang-v2"
    assert payload["items"] and payload["items"][0]["cat"] == "beach"
    assert payload["items"][0]["verified"] is True


@pytest.mark.skipif(not (V2_SNAPSHOT / "pois.json").is_file(), reason="danang-v2 snapshot missing")
def test_catalog_finds_abbreviated_cham_museum(monkeypatch):
    monkeypatch.setenv("SNAPSHOT_DIR", str(V2_SNAPSHOT))
    monkeypatch.setenv("SNAPSHOT_NAME", "danang-v2")
    response = request(app, "GET", "/v1/pois", params={"q": "Bảo tàng Chăm", "limit": 5})
    assert response.status_code == 200
    assert "Điêu khắc Chăm" in response.json()["items"][0]["name"]
