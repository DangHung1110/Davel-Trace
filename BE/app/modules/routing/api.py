"""Authenticated route-preview endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from BE.app.modules.catalog.domain import CatalogUnavailable
from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.routing.application import preview

router = APIRouter(tags=["routing"])


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
