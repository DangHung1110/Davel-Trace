"""Framework-free catalog search and display projections."""

from __future__ import annotations

import unicodedata
from typing import Any


class CatalogUnavailable(RuntimeError):
    """The configured versioned snapshot is unavailable or invalid."""


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold().strip())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def place_id(place: dict[str, Any]) -> str:
    return str(place.get("poi_id", "")).strip()


def valid_place(place: dict[str, Any]) -> bool:
    try:
        lat, lon = float(place["lat"]), float(place["lon"])
    except (KeyError, TypeError, ValueError):
        return False
    return bool(place_id(place) and str(place.get("name", "")).strip()
                and -90 <= lat <= 90 and -180 <= lon <= 180
                and isinstance(place.get("verified"), bool))


def category(place: dict[str, Any]) -> str:
    return str(place.get("cat") or place.get("type") or "other")


def search_places(places: list[dict[str, Any]], query: str, kind: str | None,
                  limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
    needle = normalize_text(query)
    requested_kind = normalize_text(kind or "")
    matches = []
    for place in places:
        haystack = " ".join([
            str(place.get("name", "")), str(place.get("type", "")),
            str(place.get("cat", "")), " ".join(map(str, place.get("tags", []))),
        ])
        if needle and needle not in normalize_text(haystack):
            continue
        if requested_kind and requested_kind not in {
            normalize_text(str(place.get("cat", ""))),
            normalize_text(str(place.get("type", ""))),
        }:
            continue
        matches.append(place)
    matches.sort(key=lambda item: (
        not item.get("verified", False),
        normalize_text(str(item.get("name", ""))), place_id(item),
    ))
    return matches[offset:offset + limit], len(matches)


def public_place(place: dict[str, Any], version: str, *, detail: bool = False) -> dict[str, Any]:
    result = {
        "poi_id": place_id(place),
        "name": str(place.get("name", "")),
        "type": str(place.get("type") or category(place)),
        "cat": category(place),
        "lat": float(place["lat"]),
        "lon": float(place["lon"]),
        "verified": bool(place.get("verified", False)),
        "source": place.get("source"),
        "fetched_at": place.get("fetched_at"),
        "snapshot_version": version,
    }
    if detail:
        for key in (
            "opening_hours", "fee", "price_level", "ticket_vnd", "ticket_note",
            "rating", "pros", "cons", "osm_evidence", "dur_source",
            "dur_confidence", "space_source", "space_confidence",
            "rain_protection", "rain_protection_source",
        ):
            if key in place:
                result[key] = place[key]
        result["opening_hours_state"] = "known" if place.get("opening_hours") else "unknown"
        result["price_state"] = "known" if any(
            place.get(key) is not None for key in ("fee", "price_level", "ticket_vnd")
        ) else "unknown"
    return result
