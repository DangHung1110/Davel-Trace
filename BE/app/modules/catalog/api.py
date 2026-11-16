"""Public, read-only HTTP surface for the versioned Da Nang catalog."""

from fastapi import APIRouter, HTTPException, Query, Request

from BE.app.modules.catalog.application import CatalogNotFound, get_place, search
from BE.app.modules.catalog.domain import CatalogUnavailable

router = APIRouter(tags=["catalog"])


@router.get("/v1/pois")
def list_pois(request: Request, q: str = Query(default="", max_length=120),
              category: str | None = Query(default=None, max_length=80),
              version: str | None = Query(default=None, max_length=128),
              limit: int = Query(default=30, ge=1, le=50),
              offset: int = Query(default=0, ge=0, le=10000)):
    try:
        payload = search(request.app.state.catalog_reader(), q, category,
                         limit=limit, offset=offset)
    except CatalogUnavailable as exc:
        raise HTTPException(status_code=503, detail="Catalog is temporarily unavailable.") from exc
    if version and version != payload["snapshot_version"]:
        raise HTTPException(status_code=404, detail="Catalog version not found.")
    return payload


@router.get("/v1/pois/{poi_id}")
def poi_detail(request: Request, poi_id: str):
    try:
        return get_place(request.app.state.catalog_reader(), poi_id)
    except CatalogNotFound as exc:
        raise HTTPException(status_code=404, detail="Place not found.") from exc
    except CatalogUnavailable as exc:
        raise HTTPException(status_code=503, detail="Catalog is temporarily unavailable.") from exc
