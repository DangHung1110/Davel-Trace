from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from BE.app.config import get_settings
from BE.app.database import get_db
from BE.app.errors import AppError
from BE.app.models.route import RouteSegment
from BE.app.models.trip import Activity, Itinerary
from BE.app.schemas.route import RoutePreview, RoutePreviewRequest
from BE.app.services.routes import fetch_route

router = APIRouter(prefix="/v1/routes", tags=["routes"])


@router.post("/preview", response_model=RoutePreview)
def route_preview(command: RoutePreviewRequest, session: Session = Depends(get_db)):
    rows = list(
        session.scalars(
            select(Activity)
            .join(Itinerary, Activity.itinerary_id == Itinerary.id)
            .where(Itinerary.trip_id == command.trip_id)
        )
    )
    by_id = {activity.id: activity for activity in rows}
    if any(activity_id not in by_id for activity_id in command.activity_ids):
        raise AppError(
            "ACTIVITY_NOT_FOUND",
            "Một hoặc nhiều hoạt động không thuộc chuyến đi",
            404,
        )
    ordered = [by_id[activity_id] for activity_id in command.activity_ids]
    coordinates = [[activity.longitude, activity.latitude] for activity in ordered]
    settings = get_settings()
    result = fetch_route(
        coordinates,
        mode=command.mode,
        base_url=settings.osrm_base_url,
        timeout_seconds=settings.route_timeout_seconds,
    )
    session.execute(delete(RouteSegment).where(RouteSegment.trip_id == command.trip_id))
    session.add(
        RouteSegment(
            trip_id=command.trip_id,
            from_activity_id=ordered[0].id,
            to_activity_id=ordered[-1].id,
            source=result["source"],
            is_real_route=result["is_real_route"],
            distance_m=result["distance_m"],
            duration_s=result["duration_s"],
            geometry=result["geometry"],
        )
    )
    session.commit()
    return result
