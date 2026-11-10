"""Optional OSRM route adapter and snapshot matrix estimator."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from BE.app.core.config import get_settings
from BE.app.modules.routing.domain import RouteResult, Stop, valid_geometry

OSRM_DEFAULT = "https://router.project-osrm.org"


class OsrmRouteError(RuntimeError):
    pass


@lru_cache(maxsize=2)
def _read_matrix(path_text: str, modified_ns: int) -> dict:
    del modified_ns
    return json.loads(Path(path_text).read_text(encoding="utf-8"))


def load_matrix() -> dict:
    configured = Path(get_settings().snapshot_dir)
    product_snapshot = Path("BE/data/snapshots") / configured.name
    if configured == Path("data/snapshots/danang-v1") and (product_snapshot / "matrix.json").is_file():
        snapshot_dir = product_snapshot
    else:
        snapshot_dir = configured if configured.is_dir() else Path("BE") / configured
    matrix_path = snapshot_dir / "matrix.json"
    if not matrix_path.is_file():
        matrix_path = Path("BE/data/snapshots") / configured.name / "matrix.json"
    return _read_matrix(str(matrix_path.resolve()), matrix_path.stat().st_mtime_ns)


def _request_json(url: str, timeout: float) -> dict:
    with urlopen(url, timeout=timeout) as response:  # noqa: S310 - fixed/validated provider host
        return json.loads(response.read().decode("utf-8"))


def route_url(stops: list[Stop], base_url: str) -> str:
    coords = ";".join(f"{stop.longitude:.6f},{stop.latitude:.6f}" for stop in stops)
    return (f"{base_url.rstrip('/')}/route/v1/driving/{quote(coords, safe=';,.-')}"
            "?overview=full&geometries=geojson&steps=false")


def osrm_route(stops: list[Stop], *, transport=None, timeout_s: float = 8.0) -> RouteResult:
    settings = get_settings()
    base = settings.osrm_base_url.strip() or OSRM_DEFAULT
    request = transport or _request_json
    try:
        payload = request(route_url(stops, base), timeout_s)
        routes = payload.get("routes") or []
        if payload.get("code") != "Ok" or not routes:
            raise OsrmRouteError("OSRM returned no route")
        first = routes[0]
        geometry = first.get("geometry") or {}
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if geometry.get("type") != "LineString" or not valid_geometry(coordinates):
            raise OsrmRouteError("OSRM returned invalid geometry")
        return RouteResult(
            quality="road_route", source="osrm", is_real_route=True,
            geometry={"type": "LineString", "coordinates": coordinates},
            distance_m=max(0, round(float(first.get("distance", 0)))),
            duration_s=max(0, round(float(first.get("duration", 0)))),
        )
    except Exception as exc:
        raise OsrmRouteError("road route unavailable") from exc


def matrix_estimate(stops: list[Stop], matrix: dict) -> RouteResult | None:
    if not isinstance(matrix, dict):
        return None
    cells = matrix.get("cells", {})
    total_m = total_s = 0
    for start, end in zip(stops, stops[1:]):
        cell = cells.get(f"{start.poi_id}->{end.poi_id}")
        if not isinstance(cell, dict):
            return None
        try:
            distance = cell.get("distance_m")
            if distance is None:
                distance = float(cell.get("km", 0)) * 1000
            duration = cell.get("duration_s")
            if duration is None:
                duration = float(cell.get("minutes", 0)) * 60
            if float(distance) <= 0 or float(duration) <= 0:
                return None
            total_m += round(float(distance))
            total_s += round(float(duration))
        except (TypeError, ValueError):
            return None
    return RouteResult(
        quality="matrix_estimate", source="snapshot_matrix", is_real_route=False,
        geometry=None, distance_m=total_m, duration_s=total_s,
        warning="Ước tính theo ma trận địa phương; không phải hình học tuyến đường.",
    )


