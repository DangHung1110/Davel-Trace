from uuid import uuid4

import pytest

from BE.app.main import app
from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.routing.domain import RouteResult
from BE.tests.support.asgi_client import request


def test_route_preview_requires_authentication():
    response = request(app, "POST", "/v1/routes/preview", json={
        "trip_id": str(uuid4()), "activity_ids": ["a", "b"], "mode": "driving",
    })
    assert response.status_code == 401


@pytest.mark.parametrize(("field", "ordered_ids"), [
    ("activity_ids", ["b", "a"]),
    ("poi_ids", ["poi-b", "poi-a"]),
])
def test_route_preview_uses_owned_trip_and_returns_quality(field, ordered_ids):
    trip_id = str(uuid4())
    original_catalog, original_matrix, original_trip = app.state.catalog_reader, app.state.matrix_reader, app.state.trip_reader
    original_route, original_estimator = app.state.route_provider, app.state.matrix_estimator
    app.state.catalog_reader = lambda: {"snapshot": "fixture-v1", "pois": [
        {"poi_id": "poi-a", "name": "A", "type": "landmark", "cat": "landmark",
         "lat": 16.0, "lon": 108.0, "verified": True},
        {"poi_id": "poi-b", "name": "B", "type": "landmark", "cat": "landmark",
         "lat": 16.1, "lon": 108.1, "verified": True},
    ]}
    app.state.matrix_reader = lambda: {"cells": {}}
    app.state.trip_reader = _TripReader(trip_id)
    route_calls = []

    def road_route(stops):
        route_calls.append([stop.poi_id for stop in stops])
        return RouteResult(
        "road_route", "osrm", True,
        {"type": "LineString", "coordinates": [[108.0, 16.0], [108.1, 16.1]]},
        1000, 300,
        )

    app.state.route_provider = road_route
    app.dependency_overrides[current_principal] = lambda: Principal(
        uuid4(), uuid4(), frozenset({"traveler"}), "test-correlation",
    )
    try:
        response = request(app, "POST", "/v1/routes/preview", json={
            "trip_id": trip_id, field: ordered_ids, "mode": "driving",
        })
        assert response.status_code == 200, response.text
        assert response.json()["quality"] == "road_route"
        assert response.json()["is_real_route"] is True
        assert route_calls == [["poi-b", "poi-a"]]
    finally:
        app.state.catalog_reader, app.state.matrix_reader, app.state.trip_reader = original_catalog, original_matrix, original_trip
        app.state.route_provider, app.state.matrix_estimator = original_route, original_estimator
        app.dependency_overrides.pop(current_principal, None)


@pytest.mark.parametrize("field", ["activity_ids", "poi_ids"])
def test_foreign_trip_is_not_disclosed(field):
    trip_id = str(uuid4())
    original, original_trip = app.state.catalog_reader, app.state.trip_reader
    app.state.catalog_reader = lambda: {"snapshot": "fixture-v1", "pois": []}
    app.state.trip_reader = _TripReader(trip_id, missing=True)
    app.dependency_overrides[current_principal] = lambda: Principal(
        uuid4(), uuid4(), frozenset({"traveler"}), "test-correlation",
    )
    try:
        response = request(app, "POST", "/v1/routes/preview", json={
            "trip_id": trip_id, field: ["a", "b"],
        })
        assert response.status_code == 404
        assert "another" not in response.text.lower()
    finally:
        app.state.catalog_reader, app.state.trip_reader = original, original_trip
        app.dependency_overrides.pop(current_principal, None)


class _TripReader:
    def __init__(self, trip_id, *, missing=False):
        self.trip_id = trip_id
        self.missing = missing

    def get(self, _principal, requested):
        if self.missing or str(requested) != self.trip_id:
            raise LookupError("private resource")
        return {"days": [{"activities": [
            {"id": "a", "title": "A", "poi_id": "poi-a"},
            {"id": "b", "title": "B", "poi_id": "poi-b"},
        ]}]}
