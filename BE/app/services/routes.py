from __future__ import annotations

from typing import Any

import httpx


def fallback_route(coordinates: list[list[float]], warning: str | None = None) -> dict:
    return {
        "source": "fallback",
        "is_real_route": False,
        "distance_m": 0,
        "duration_s": 0,
        "geometry": coordinates,
        "warning": warning
        or "Không lấy được tuyến thật; đường thẳng chỉ dùng để tham khảo hiển thị.",
    }


def parse_osrm_route(payload: dict[str, Any]) -> dict:
    routes = payload.get("routes") or []
    if payload.get("code") != "Ok" or not routes:
        raise ValueError("OSRM did not return a route")
    route = routes[0]
    geometry = route.get("geometry", {}).get("coordinates") or []
    if len(geometry) < 2:
        raise ValueError("OSRM route has no usable geometry")
    return {
        "source": "osrm",
        "is_real_route": True,
        "distance_m": int(round(float(route.get("distance", 0)))),
        "duration_s": int(round(float(route.get("duration", 0)))),
        "geometry": geometry,
        "warning": None,
    }


def fetch_route(
    coordinates: list[list[float]],
    *,
    mode: str,
    base_url: str,
    timeout_seconds: float,
) -> dict:
    coordinate_path = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
    profile = {"driving": "driving", "walking": "walking", "cycling": "cycling"}[mode]
    url = f"{base_url.rstrip('/')}/route/v1/{profile}/{coordinate_path}"
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(
                url, params={"overview": "full", "geometries": "geojson", "steps": "false"}
            )
            response.raise_for_status()
            return parse_osrm_route(response.json())
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return fallback_route(coordinates, f"OSRM không khả dụng ({type(exc).__name__}); đường hiển thị không phải tuyến thật.")
