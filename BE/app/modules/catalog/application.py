"""Public catalog application queries consumed by HTTP and other capabilities."""

from __future__ import annotations

from BE.app.modules.catalog.domain import place_id, public_place, search_places


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


__all__ = ["CatalogNotFound", "get_place", "resolve_place", "search"]
