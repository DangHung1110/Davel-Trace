"""Framework-free route quality and result values."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Stop:
    activity_id: str
    title: str
    poi_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class RouteResult:
    quality: str
    source: str
    is_real_route: bool
    geometry: dict | None
    distance_m: int
    duration_s: int
    warning: str | None = None

    def to_public(self) -> dict:
        return {
            "quality": self.quality,
            "source": self.source,
            "is_real_route": self.is_real_route,
            "geometry": self.geometry,
            "distance_m": self.distance_m,
            "duration_s": self.duration_s,
            "warning": self.warning,
        }


def valid_geometry(coordinates: object) -> bool:
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return False
    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
            return False
        try:
            lon, lat = float(coordinate[0]), float(coordinate[1])
        except (TypeError, ValueError):
            return False
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            return False
    return True


def linear_interpolation(stops: list[Stop]) -> RouteResult:
    """Last-resort display line; it is never represented as a road route."""
    coordinates = [[stop.longitude, stop.latitude] for stop in stops]
    distance_m = 0
    for first, second in zip(coordinates, coordinates[1:]):
        lon1, lat1 = map(math.radians, first)
        lon2, lat2 = map(math.radians, second)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        distance_m += round(6_371_000 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value)))
    return RouteResult(
        quality="interpolated", source="straight_line", is_real_route=False,
        geometry={"type": "LineString", "coordinates": coordinates},
        distance_m=distance_m, duration_s=0,
        warning="Đường nối nội suy để minh họa thứ tự điểm; không phải tuyến đường thực tế.",
    )
