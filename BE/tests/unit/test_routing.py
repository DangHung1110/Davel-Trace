from BE.app.modules.routing.domain import RouteResult, Stop, linear_interpolation, valid_geometry
from BE.app.modules.routing.infrastructure import (
    OsrmRouteError, matrix_estimate, osrm_route, route_url,
)
from BE.app.modules.routing.application import preview


STOPS = [
    Stop("a", "A", "poi-a", 16.0, 108.2),
    Stop("b", "B", "poi-b", 16.1, 108.3),
]


def test_route_url_uses_ordered_lon_lat_and_safe_route_shape():
    url = route_url(STOPS, "https://router.example/")
    assert "/16.0" not in url
    assert "/108.200000,16.000000;108.300000,16.100000?" in url
    assert "geometries=geojson" in url


def test_osrm_success_is_the_only_real_road_route():
    payload = {"code": "Ok", "routes": [{
        "distance": 1200.4, "duration": 300.2,
        "geometry": {"type": "LineString", "coordinates": [[108.2, 16.0], [108.3, 16.1]]},
    }]}
    result = osrm_route(STOPS, transport=lambda _url, _timeout: payload)
    assert result.quality == "road_route"
    assert result.source == "osrm"
    assert result.is_real_route is True
    assert result.distance_m == 1200


def test_bad_geometry_is_rejected_and_matrix_stays_an_estimate():
    with __import__("pytest").raises(OsrmRouteError):
        osrm_route(STOPS, transport=lambda *_: {
            "code": "Ok", "routes": [{"geometry": {"type": "LineString", "coordinates": [[999, 999]]}}],
        })
    result = matrix_estimate(STOPS, {"cells": {
        "poi-a->poi-b": {"km": 4.25, "minutes": 9},
    }})
    assert result is not None
    assert result.quality == "matrix_estimate"
    assert result.is_real_route is False
    assert result.geometry is None
    assert result.distance_m == 4250


def test_osrm_timeout_is_bounded_and_reported_as_unavailable():
    def timeout_transport(_url, timeout):
        assert timeout == 8.0
        raise TimeoutError("provider timeout")

    with __import__("pytest").raises(OsrmRouteError):
        osrm_route(STOPS, transport=timeout_transport)


def test_missing_matrix_is_unavailable_and_geometry_validation_is_bounded():
    assert matrix_estimate(STOPS, {}) is None
    assert not valid_geometry([[108.2, 16.0]])
    assert valid_geometry([[108.2, 16.0], [108.3, 16.1]])


def test_explicit_unavailable_result_is_not_a_route():
    result = RouteResult("unavailable", "none", False, None, 0, 0, "offline")
    assert result.to_public()["is_real_route"] is False


def test_interpolation_fallback_is_explicit_and_not_a_road_route():
    result = linear_interpolation(STOPS)
    assert result.quality == "interpolated"
    assert result.source == "straight_line"
    assert result.is_real_route is False
    assert result.geometry["coordinates"] == [[108.2, 16.0], [108.3, 16.1]]
    assert "không phải tuyến đường thực tế" in result.warning


def test_unknown_catalog_activity_is_skipped_with_explicit_warning():
    catalog = {"snapshot": "fixture-v1", "pois": [
        {"poi_id": "poi-a", "name": "A", "type": "landmark", "lat": 16.0, "lon": 108.2},
        {"poi_id": "poi-b", "name": "B", "type": "landmark", "lat": 16.1, "lon": 108.3},
    ]}
    activities = [
        {"id": "a", "title": "A", "poi_id": "poi-a"},
        {"id": "retired", "title": "Retired stop", "poi_id": "removed-poi"},
        {"id": "b", "title": "B", "poi_id": "poi-b"},
    ]
    calls = []

    class TripReader:
        def get(self, _principal, _trip_id):
            return {"days": [{"activities": activities}]}

    result = preview(
        principal=object(), trip_id="00000000-0000-0000-0000-000000000001",
        activity_ids=["a", "retired", "b"], catalog=catalog, matrix={},
        trip_reader=TripReader(),
        route_provider=lambda stops: calls.extend(stops) or RouteResult(
            "road_route", "osrm", True,
            {"type": "LineString", "coordinates": [[108.2, 16.0], [108.3, 16.1]]},
            1200, 300,
        ),
        estimate_provider=lambda *_: None,
    )

    assert [stop.activity_id for stop in calls] == ["a", "b"]
    assert result["quality"] == "road_route"
    assert "đã được bỏ qua" in result["warning"]


def test_preview_falls_back_to_interpolation_when_route_and_matrix_fail():
    catalog = {"snapshot": "fixture-v1", "pois": [
        {"poi_id": "poi-a", "name": "A", "type": "landmark", "lat": 16.0, "lon": 108.2},
        {"poi_id": "poi-b", "name": "B", "type": "landmark", "lat": 16.1, "lon": 108.3},
    ]}

    class TripReader:
        def get(self, _principal, _trip_id):
            return {"days": [{"activities": [
                {"id": "a", "title": "A", "poi_id": "poi-a"},
                {"id": "b", "title": "B", "poi_id": "poi-b"},
            ]}]}

    result = preview(
        principal=object(), trip_id="00000000-0000-0000-0000-000000000001",
        activity_ids=["a", "b"], catalog=catalog, matrix={},
        trip_reader=TripReader(),
        route_provider=lambda *_: (_ for _ in ()).throw(TimeoutError()),
        estimate_provider=lambda stops, matrix: matrix_estimate(stops, matrix),
    )

    assert result["quality"] == "interpolated"
    assert result["is_real_route"] is False
    assert result["geometry"]["coordinates"] == [[108.2, 16.0], [108.3, 16.1]]
