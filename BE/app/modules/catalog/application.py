"""Public catalog application queries consumed by HTTP and other capabilities."""

from __future__ import annotations

from BE.app.modules.catalog.domain import name_words, named_terms_in_order, place_id, public_place, search_places


class CatalogNotFound(LookupError):
    pass


def search(catalog: dict, query: str = "", kind: str | None = None, *,
           limit: int = 30, offset: int = 0) -> dict:
    rows, total = search_places(catalog["pois"], query, kind, limit, offset)
    return {
        "snapshot_version": catalog["snapshot"],
        "items": [public_place(row, catalog["snapshot"]) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_place(catalog: dict, identifier: str) -> dict:
    row = next((item for item in catalog["pois"] if place_id(item) == identifier), None)
    if row is None:
        raise CatalogNotFound(identifier)
    return public_place(row, catalog["snapshot"], detail=True)


def resolve_place(catalog: dict, identifier: str) -> dict | None:
    """Public cross-capability contract; does not expose snapshot infrastructure."""
    try:
        return get_place(catalog, identifier)
    except CatalogNotFound:
        return None


def normalize_place_name(value: str) -> str:
    return " ".join(name_words(value))


def resolve_name_candidates(places: list[dict], name: str) -> list[dict]:
    """Resolve extracted names locally; never pick a first ambiguous result."""
    needle = normalize_place_name(name)
    if not needle:
        return []
    terms = needle.split()
    exact, partial, abbreviated = {}, {}, {}
    for place in places:
        identifier = place_id(place)
        if place.get("verified") is not True or not identifier:
            continue
        aliases = place.get("aliases")
        names = [str(place.get("name") or "")]
        if isinstance(aliases, list):
            names.extend(value for value in aliases if isinstance(value, str))
        names = [normalize_place_name(value) for value in names]
        if needle in names:
            exact[identifier] = place
        elif any(f" {needle} " in f" {value} " for value in names):
            partial[identifier] = place
        elif len(terms) >= 3 and any(named_terms_in_order(terms, value) for value in names):
            abbreviated[identifier] = place
    return sorted((exact or partial or abbreviated).values(), key=lambda row: (
        normalize_place_name(str(row.get("name") or "")), place_id(row),
    ))


__all__ = ["CatalogNotFound", "get_place", "normalize_place_name", "resolve_place", "resolve_name_candidates", "search"]
