"""Authenticated route previews and public local-map byte serving."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import FileResponse

from BE.app.modules.catalog.domain import CatalogUnavailable
from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.routing.application import preview

router = APIRouter(tags=["routing"])
MAP_ARCHIVE_PATH = Path(__file__).resolve().parents[4] / "data" / "danang.pmtiles"


@router.get("/v1/maps/danang.pmtiles")
def map_archive():
    """Public map data, including byte ranges required by PMTiles clients."""
    if not MAP_ARCHIVE_PATH.is_file():
        raise HTTPException(status_code=503, detail="Bản đồ tạm thời chưa khả dụng.")
    return FileResponse(MAP_ARCHIVE_PATH, media_type="application/vnd.pmtiles",
                        headers={"Cache-Control": "public, max-age=86400"})


class RoutePreviewBody(BaseModel):
    trip_id: UUID
    activity_ids: list[str] = Field(min_length=2, max_length=25)
    mode: str = Field(default="driving", pattern="^driving$")


@router.post("/v1/routes/preview")
def route_preview(request: Request, body: RoutePreviewBody,
                  current: Principal = Depends(current_principal)):
    try:
        catalog = request.app.state.catalog_reader()
    except (OSError, CatalogUnavailable) as exc:
        raise HTTPException(status_code=503, detail="Catalog is temporarily unavailable.") from exc
    try:
        matrix = request.app.state.matrix_reader()
    except (OSError, CatalogUnavailable):
        matrix = {}
    try:
        return preview(current, str(body.trip_id), body.activity_ids, catalog, matrix,
                       request.app.state.trip_reader,
                       request.app.state.route_provider,
                       request.app.state.matrix_estimator)
    except LookupError as exc:
        raise IdentityError("NOT_FOUND", "Không tìm thấy hoạt động trong chuyến đi.", 404) from exc
    except ValueError as exc:
        raise IdentityError("VALIDATION_ERROR", str(exc), 422) from exc
