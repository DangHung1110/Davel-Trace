"""A device position (a GPS fix) as the place a day starts from.

Every leg the planner charges (T9), schedules and gates (B3) comes from the OSRM matrix
(research R4), and only snapshot places own a row. A fix borrows rows (design A, chosen
2026-11-26 over a straight-line estimate and a live OSRM call): the places with a row
nearest to it are its ANCHORS, and a leg from the fix is the best way through one of
them, the short ride to the anchor plus the anchor's real leg:

    minutes(fix -> b) = round(min over anchors q of [ride(fix, q) + matrix(q -> b)])
    ride(fix, q)      = straight km x ROAD_FACTOR at SPEED_KMH

A fix within AT_PLACE_KM of a place is AT that place: its one anchor, whose ride rounds
to 0 minutes, so a fix at the hotel plans exactly like the hotel. Otherwise the
ANCHORS nearest places are tried. The fix becomes a start of its own (`start_id`,
"@gps:<lat>,<lon>") whose row `matrix.with_starts` serves, so the solver, the order
search, gate B3 and the plan's segments read it like any other row; its cells say
`source: gps_estimate`.

Measured on danang-v2 (BE/tools/gps_origin_error.py), minutes of error per leg:
- 510 random points on Da Nang roads against a local OSRM on the same motorbike
  profile: city core mean 1.2 (p90 3), 1.4 % of legs short by more than 3 min; by
  distance to the nearest place: 0.3 within 0.2 km, 0.8 at 0.2-0.5 km, 1.2 at
  0.5-1 km, 2.1 at 1-2 km, 2.9 at 2-3 km (p90 7), 3.9 at 3-5 km (p90 12). A straight
  line alone: city core 2.1, 7 % short by more than 3 min. One anchor only: 1.9.
- each of the 1009 places with a row playing the fix, its own row hidden: mean 0.64;
  a fix 5-50 m from a hotel: 0.01 (that hotel's own legs).
50 % of the city core's roads are within 0.5 km of a place with a row, 71 % within
1 km, 93 % within 3 km: hence WARN_KM and MAX_KM.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

# Median road km / straight km and road km per OSRM hour over the 1,016,528 pairs of
# the danang-v2 matrix more than 50 m apart (motorbike profile).
ROAD_FACTOR = 1.19
SPEED_KMH = 29.6
# Closer than this to a place, the ride to it rounds to 0 minutes: the fix is there.
AT_PLACE_KM = 0.2
# How many of the nearest places a fix away from every place may go through.
ANCHORS = 3
# Farther from every place with a row than this, the legs are a rough guess (mean
# error 2 min or more, p90 5+): the fix is used and the plan says so.
WARN_KM = 1.0
# Farther than this (p90 12 min), or outside Da Nang altogether, the fix is not used:
# the day starts where it would have without it.
MAX_KM = 3.0
# A fix whose own uncertainty is this wide cannot tell which street it is on.
MAX_ACCURACY_M = 1000.0
START_PREFIX = "@gps:"
EARTH_KM = 6371.0088


def straight_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_KM * math.asin(math.sqrt(min(1.0, a)))


def ride(km: float) -> tuple[float, float]:
    """(minutes, road km) of the ride from a fix to a place `km` away in a straight line."""
    road_km = km * ROAD_FACTOR
    return road_km / SPEED_KMH * 60.0, road_km


def start_id(lat: float, lon: float) -> str:
    """The id a fix starts from: stable for one position (~1 m), never a poi_id."""
    return f"{START_PREFIX}{lat:.5f},{lon:.5f}"


def is_start(pid: str | None) -> bool:
    return bool(pid) and str(pid).startswith(START_PREFIX)


@dataclass(frozen=True)
class Anchor:
    """A place with a matrix row a fix may go through, and the ride to it."""

    poi_id: str
    km: float
    access_min: float
    access_km: float


@dataclass(frozen=True)
class GpsStart:
    """A usable fix: where it is and its anchors, nearest first."""

    start_id: str
    lat: float
    lon: float
    anchors: tuple[Anchor, ...]

    @property
    def nearest(self) -> Anchor:
        return self.anchors[0]

    @property
    def far(self) -> bool:
        """Far enough from every place that the plan must say its legs are a guess."""
        return self.nearest.km > WARN_KM

    def row(self) -> tuple[tuple[str, float, float], ...]:
        """What `matrix.with_starts` builds the fix's row from."""
        return tuple((a.poi_id, a.access_min, a.access_km) for a in self.anchors)


def _anchors(by_id: Mapping, cells: Mapping) -> list[tuple[str, float, float]]:
    """(poi_id, lat, lon) of every place that owns a matrix row and has coordinates."""
    rows = getattr(cells, "row_ids", None)
    if rows is None:
        rows = {key.split("->", 1)[0] for key in cells}
    out = []
    for pid in rows:
        poi = by_id.get(pid) or {}
        lat, lon = poi.get("lat"), poi.get("lon")
        if lat is not None and lon is not None and not is_start(pid):
            out.append((pid, float(lat), float(lon)))
    return out


def locate(lat: float, lon: float, by_id: Mapping, cells: Mapping,
           accuracy_m: float | None = None) -> tuple[GpsStart | None, str | None]:
    """A fix -> (its start, None) or (None, why it cannot start a day).

    `by_id`: the snapshot's places (coordinates, names); `cells`: the matrix. The
    reason is a plan warning (no diacritics, like the router's other warnings).
    """
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, "khong dung vi tri GPS: toa do khong hop le"
    if accuracy_m is not None and accuracy_m > MAX_ACCURACY_M:
        return None, (f"khong dung vi tri GPS: sai so {accuracy_m:.0f} m "
                      f"(toi da {MAX_ACCURACY_M:.0f} m)")
    near = sorted((straight_km(lat, lon, a_lat, a_lon), pid)
                  for pid, a_lat, a_lon in _anchors(by_id, cells))
    if not near:
        return None, "khong dung vi tri GPS: chua co dia diem nao co toa do va ma tran"
    km, _pid = near[0]
    if km > MAX_KM:
        where = "ngoai vung Da Nang, " if km > 20 else ""
        return None, (f"khong dung vi tri GPS: {where}cach dia diem co du lieu gan nhat "
                      f"{km:.1f} km (toi da {MAX_KM:.0f} km)")
    picked = near[:1] if km <= AT_PLACE_KM else near[:ANCHORS]
    anchors = tuple(Anchor(pid, d, *ride(d)) for d, pid in picked)
    return GpsStart(start_id=start_id(lat, lon), lat=lat, lon=lon, anchors=anchors), None


def report(start: GpsStart, by_id: Mapping) -> dict:
    """What the plan says about a fix it started from (`plan["gps_origin"]`)."""
    nearest = start.nearest
    return {"used": True, "lat": round(start.lat, 5), "lon": round(start.lon, 5),
            "origin_id": start.start_id, "anchor_poi_id": nearest.poi_id,
            "anchor_name": (by_id.get(nearest.poi_id) or {}).get("name") or nearest.poi_id,
            "anchor_m": int(round(nearest.km * 1000)),
            "access_min": round(nearest.access_min, 1), "estimate": True}


def far_warning(start: GpsStart, by_id: Mapping) -> str:
    """The plan warning of a fix more than WARN_KM from every place."""
    nearest = start.nearest
    name = (by_id.get(nearest.poi_id) or {}).get("name") or nearest.poi_id
    return (f"vi tri GPS cach dia diem co du lieu gan nhat ({name}) {nearest.km:.1f} km: "
            "gio den diem dau la uoc luong, co the lech vai phut")
