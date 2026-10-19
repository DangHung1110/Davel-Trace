from BE.app.services.routes import fallback_route, parse_osrm_route


def test_fallback_is_never_a_real_route():
    result = fallback_route([[108.22, 16.06], [108.25, 16.08]])
    assert result["source"] == "fallback"
    assert result["is_real_route"] is False
    assert result["warning"]


def test_parse_osrm_route_labels_real_geometry():
    result = parse_osrm_route(
        {
            "code": "Ok",
            "routes": [
                {
                    "distance": 1250.5,
                    "duration": 420.0,
                    "geometry": {"coordinates": [[108.22, 16.06], [108.25, 16.08]]},
                }
            ],
        }
    )
    assert result["source"] == "osrm"
    assert result["is_real_route"] is True
    assert result["distance_m"] == 1250
