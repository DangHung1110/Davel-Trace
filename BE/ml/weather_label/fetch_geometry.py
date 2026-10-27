"""Fetch linked OSM geometry for the T063 weather labeler.

The snapshot's node-only OSM cache proves distance, not containment.  This
utility takes a JSON list of POI rows ``{poi_id, lat, lon, name}`` and asks
Overpass for nearby *ways/relations* that carry weather-relevant tags, with
``out center geom tags`` so the labeler receives real polygon vertices.

Association rules (deliberately strict):

* only ``way``/``relation`` elements with actual geometry are considered;
* a node, a bare ``center`` or a proximity match is never accepted;
* an element is linked only when its name matches the POI or its (closed)
  polygon/relation member ring contains the POI coordinate.

Raw payloads are written only to the caller-specified ``--output`` path
(normally TEMP, never the repo).  No snapshot is touched.

CLI::

    python -m BE.ml.weather_label.fetch_geometry \
        --input weather_review_200.json --output %TEMP%/weather_geometry.json

Dependency-free: stdlib ``urllib`` only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Sequence

PRIMARY_ENDPOINT = "https://overpass-api.de/api/interpreter"
MIRROR_ENDPOINT = "https://overpass.kumi.systems/api/interpreter"
ENDPOINTS = (PRIMARY_ENDPOINT, MIRROR_ENDPOINT)

#: OSM keys that carry space / rain-protection evidence for the labeler.
RELEVANT_KEYS = (
    "building",
    "covered",
    "indoor",
    "outdoor",
    "shelter",
    "weather_protection",
    "leisure",
    "natural",
    "tourism",
    "historic",
)
SHELTER_AMENITIES = ("shelter", "weather_shelter")

DEFAULT_BATCH_SIZE = 20
DEFAULT_RADIUS_M = 75.0
DEFAULT_TIMEOUT_S = 120
DEFAULT_DELAY_S = 1.0

USER_AGENT = "Davel-Trace/research (T063 weather geometry)"

#: transport(url, query, timeout) -> decoded Overpass JSON payload.
Transport = Callable[[str, str, float], dict]
NowFn = Callable[[], datetime]
SleepFn = Callable[[float], None]


def _fmt_number(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return repr(number)


def _point_clauses(lat: float, lon: float, radius: float) -> list[str]:
    key_re = "^(?:" + "|".join(RELEVANT_KEYS) + ")$"
    amenity_re = "^(?:" + "|".join(SHELTER_AMENITIES) + ")$"
    prefix = f"around:{_fmt_number(radius)},{_fmt_number(lat)},{_fmt_number(lon)}"
    return [
        f'way({prefix})[~"{key_re}"~"."];',
        f'relation({prefix})[~"{key_re}"~"."];',
        f'way({prefix})["amenity"~"{amenity_re}"];',
        f'relation({prefix})["amenity"~"{amenity_re}"];',
    ]


def build_query(points: Iterable[tuple[float, float]],
                radius: float = DEFAULT_RADIUS_M,
                timeout: float = DEFAULT_TIMEOUT_S) -> str:
    """Build one Overpass QL request for a batch of ``(lat, lon)`` points."""
    clauses: list[str] = []
    for lat, lon in points:
        clauses.extend(_point_clauses(lat, lon, radius))
    body = "\n  ".join(clauses)
    return (f"[out:json][timeout:{int(timeout)}];\n(\n  {body}\n);\n"
            f"out center geom tags;")


def default_transport(url: str, query: str, timeout: float) -> dict:
    """POST an Overpass query and return the decoded JSON payload."""
    data = urllib.parse.urlencode({"data": query}).encode()
    request = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"unexpected Overpass payload from {url}")
    return payload


def _request(query: str, transport: Transport, endpoints: Sequence[str],
             timeout: float) -> tuple[dict, str]:
    errors: list[str] = []
    for endpoint in endpoints:
        try:
            payload = transport(endpoint, query, timeout)
            if not isinstance(payload, dict):
                raise TypeError("transport must return a dict payload")
            return payload, endpoint
        except Exception as exc:  # noqa: BLE001 - try the mirror, else report
            errors.append(f"{endpoint}: {exc}")
    raise RuntimeError("all Overpass endpoints failed: " + "; ".join(errors))


def _name_key(value: Any) -> str:
    """Accent-insensitive, punctuation-insensitive comparison key."""
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _element_names(tags: dict) -> set[str]:
    return {_name_key(tags.get(key)) for key in
            ("name", "name:en", "alt_name", "official_name")
            if tags.get(key)}


def _is_relevant(tags: dict) -> bool:
    if any(key in tags for key in RELEVANT_KEYS):
        return True
    return tags.get("amenity") in SHELTER_AMENITIES


def _coords(geometry: Any) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    if not isinstance(geometry, (list, tuple)):
        return points
    for point in geometry:
        try:
            if isinstance(point, dict):
                points.append((float(point["lat"]), float(point["lon"])))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
            else:
                return []
        except (KeyError, TypeError, ValueError):
            return []
    return points


def _is_closed(points: list[tuple[float, float]]) -> bool:
    return (len(points) >= 4
            and abs(points[0][0] - points[-1][0]) < 1e-7
            and abs(points[0][1] - points[-1][1]) < 1e-7)


def _rings(element: dict) -> list[list[tuple[float, float]]]:
    """Closed rings from a way's geometry or a relation's member geometries."""
    rings: list[list[tuple[float, float]]] = []
    if element.get("type") == "node":
        return rings
    own = _coords(element.get("geometry"))
    if _is_closed(own):
        rings.append(own)
    members = element.get("members")
    if isinstance(members, list):
        for member in members:
            if not isinstance(member, dict):
                continue
            ring = _coords(member.get("geometry"))
            if _is_closed(ring):
                rings.append(ring)
    return rings


def _has_geometry(element: dict) -> bool:
    if element.get("type") == "node":
        return False
    if _coords(element.get("geometry")):
        return True
    members = element.get("members")
    return bool(isinstance(members, list) and any(
        isinstance(member, dict) and _coords(member.get("geometry"))
        for member in members))


def _point_in_ring(lat: float, lon: float,
                   ring: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if ((yi > lat) != (yj > lat)) and (
                lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _contains(element: dict, lat: float, lon: float) -> bool:
    return any(_point_in_ring(lat, lon, ring) for ring in _rings(element))


def _is_linked(poi: dict, element: dict) -> bool:
    """True only for real geometry linked by name or polygon containment."""
    if element.get("type") not in ("way", "relation"):
        return False
    if not _has_geometry(element):
        return False
    tags = element.get("tags")
    if not isinstance(tags, dict) or not _is_relevant(tags):
        return False
    names = _element_names(tags)
    poi_name = _name_key(poi.get("name"))
    if poi_name and poi_name in names:
        return True
    return _contains(element, float(poi["lat"]), float(poi["lon"]))


def _prepare_rows(rows: Any) -> list[dict]:
    if isinstance(rows, dict):
        for key in ("pois", "rows", "items"):
            if isinstance(rows.get(key), list):
                rows = rows[key]
                break
        else:
            raise ValueError("input object must contain a 'pois' list")
    if not isinstance(rows, list):
        raise ValueError("input must be a JSON list of POI rows")

    prepared: list[dict] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"row {index} is not an object")
        if row.get("poi_id") is None:
            raise ValueError(f"row {index} has no poi_id")
        item = {"poi_id": row["poi_id"], "name": str(row.get("name") or "")}
        try:
            item["lat"] = float(row["lat"])
            item["lon"] = float(row["lon"])
            item["queryable"] = True
        except (KeyError, TypeError, ValueError):
            item["lat"] = None
            item["lon"] = None
            item["queryable"] = False
        prepared.append(item)
    return prepared


def fetch_geometry(rows: Any, *, transport: Transport | None = None,
                   sleep: SleepFn | None = None,
                   batch_size: int = DEFAULT_BATCH_SIZE,
                   radius: float = DEFAULT_RADIUS_M,
                   timeout: float = DEFAULT_TIMEOUT_S,
                   delay: float = DEFAULT_DELAY_S,
                   endpoints: Sequence[str] = ENDPOINTS,
                   now: NowFn | None = None) -> dict:
    """Fetch geometry for ``rows`` and return ``{source, fetched_at, by_poi}``.

    Parameters are injectable for tests: ``transport`` replaces the urllib
    call, ``sleep`` replaces ``time.sleep`` and ``now`` replaces the clock.
    No network access happens unless the default transport is used.
    """
    transport = transport or default_transport
    sleep = sleep or time.sleep
    now = now or (lambda: datetime.now(timezone.utc))
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    prepared = _prepare_rows(rows)
    by_poi: dict[str, list[dict]] = {}
    buckets: dict[str, dict[tuple[Any, Any], dict]] = {}
    for row in prepared:
        key = str(row["poi_id"])
        by_poi.setdefault(key, [])
        buckets.setdefault(key, {})

    queryable = [row for row in prepared if row["queryable"]]
    endpoint_list = tuple(endpoints)
    source = endpoint_list[0] if endpoint_list else PRIMARY_ENDPOINT

    for start in range(0, len(queryable), batch_size):
        batch = queryable[start:start + batch_size]
        if start and delay > 0:
            sleep(delay)
        query = build_query(
            [(row["lat"], row["lon"]) for row in batch],
            radius=radius, timeout=timeout)
        payload, source = _request(query, transport, endpoint_list, timeout)
        elements = payload.get("elements")
        if not isinstance(elements, list):
            continue
        for element in elements:
            if not isinstance(element, dict):
                continue
            for row in batch:
                if not _is_linked(row, element):
                    continue
                bucket = buckets[str(row["poi_id"])]
                element_key = (element.get("type"), element.get("id"))
                bucket.setdefault(element_key, element)

    for key, bucket in buckets.items():
        by_poi[key] = list(bucket.values())

    fetched_at = now().astimezone(timezone.utc).isoformat()
    if fetched_at.endswith("+00:00"):
        fetched_at = fetched_at[:-6] + "Z"
    return {"source": source, "fetched_at": fetched_at, "by_poi": by_poi}


def load_rows(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_output(path: str, payload: dict) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch linked OSM geometry for T063 weather labels")
    parser.add_argument("--input", required=True,
                        help="JSON list of {poi_id, lat, lon, name} rows")
    parser.add_argument("--output", required=True,
                        help="output JSON path (normally TEMP, never the repo)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--radius", type=float, default=DEFAULT_RADIUS_M,
                        help="search radius per POI in metres")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_S,
                        help="seconds between batch requests")
    parser.add_argument("--endpoint", action="append", dest="endpoints",
                        help="override Overpass endpoint (repeatable)")
    args = parser.parse_args(argv)

    rows = load_rows(args.input)
    result = fetch_geometry(
        rows,
        batch_size=args.batch_size,
        radius=args.radius,
        timeout=args.timeout,
        delay=args.delay,
        endpoints=tuple(args.endpoints) if args.endpoints else ENDPOINTS,
    )
    write_output(args.output, result)
    returned = sum(1 for elements in result["by_poi"].values() if elements)
    print(f"geometry for {returned}/{len(result['by_poi'])} POIs "
          f"-> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
