"""Framework-free catalog search and display projections."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


class CatalogUnavailable(RuntimeError):
    """The configured versioned snapshot is unavailable or invalid."""


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold().strip().replace("đ", "d"))
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def name_words(value: str) -> list[str]:
    return re.findall(r"\w+", normalize_text(value))


def named_terms_in_order(terms: list[str], name: str) -> bool:
    available = iter(name_words(name))
    return bool(terms) and all(any(term == word for word in available) for term in terms)


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
    terms = name_words(query)
    needle = " ".join(terms)
    requested_kind = normalize_text(kind or "")
    matches = []
    for place in places:
        # danang-v2.1 keeps excluded records (karaoke, hostess bars, places the user
        # deleted) for traceability only: never offered in search, still found by id
        # so an older trip that holds one keeps its route.
        if place.get("status") == "excluded":
            continue
        if requested_kind and requested_kind not in {
            normalize_text(str(place.get("cat", ""))),
            normalize_text(str(place.get("type", ""))),
        }:
            continue
        name = str(place.get("name", ""))
        aliases = place.get("aliases")
        names = [name, *(alias for alias in aliases if isinstance(alias, str))] if isinstance(aliases, list) else [name]
        normalized = [" ".join(name_words(label)) for label in names]
        if not needle:
            rank = 0
        elif needle in normalized:
            rank = 0
        elif any(needle in label for label in normalized):
            rank = 1
        elif any(named_terms_in_order(terms, label) for label in names):
            rank = 2
        elif needle in " ".join(name_words(" ".join([
            name, str(place.get("type", "")), str(place.get("cat", "")),
            " ".join(map(str, place.get("tags", []))),
        ]))):
            rank = 3
        else:
            continue
        matches.append((rank, place))
    matches.sort(key=lambda item: (
        item[0],
        not item[1].get("verified", False),
        normalize_text(str(item[1].get("name", ""))), place_id(item[1]),
    ))
    return [place for _, place in matches[offset:offset + limit]], len(matches)


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
