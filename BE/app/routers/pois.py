from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Query

from BE.app.config import get_settings
from BE.app.errors import AppError
from BE.app.repositories.poi_catalog import PoiCatalog
from BE.app.schemas.poi import PoiList, PoiSummary

router = APIRouter(prefix="/v1/pois", tags=["pois"])


@lru_cache(maxsize=4)
def _catalog(path: str) -> PoiCatalog:
    return PoiCatalog(Path(path))


def catalog() -> PoiCatalog:
    return _catalog(str(get_settings().snapshot_path))


@router.get("", response_model=PoiList)
def search_pois(
    q: str = "",
    limit: int = Query(default=20, ge=1, le=50),
    verified_only: bool = False,
):
    try:
        items = catalog().search(q, limit=limit, verified_only=verified_only)
        snapshot, fetched_at = catalog().metadata()
    except FileNotFoundError as exc:
        raise AppError(
            "SNAPSHOT_MISSING", "POI snapshot chưa sẵn sàng", 503, {"path": str(exc)}
        ) from exc
    return {
        "items": [PoiSummary.model_validate(item) for item in items],
        "snapshot": snapshot,
        "fetched_at": fetched_at,
    }


@router.get("/{poi_id}")
def get_poi(poi_id: str):
    try:
        poi = catalog().get(poi_id)
    except FileNotFoundError as exc:
        raise AppError("SNAPSHOT_MISSING", "POI snapshot chưa sẵn sàng", 503) from exc
    if poi is None:
        raise AppError("POI_NOT_FOUND", "Không tìm thấy địa điểm", 404)
    return poi
