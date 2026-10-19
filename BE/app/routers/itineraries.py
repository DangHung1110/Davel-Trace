from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from BE.app.database import get_db
from BE.app.schemas.trip import (
    ActivityCreate,
    ActivityOrder,
    ActivityUpdate,
    ItineraryRead,
)
from BE.app.services import itineraries as service

router = APIRouter(prefix="/v1", tags=["itinerary"])


@router.get("/trips/{trip_id}/itinerary", response_model=ItineraryRead)
def get_itinerary(trip_id: str, session: Session = Depends(get_db)):
    return service.itinerary_payload(service.get_itinerary(session, trip_id))


@router.post(
    "/trips/{trip_id}/activities",
    response_model=ItineraryRead,
    status_code=status.HTTP_201_CREATED,
)
def add_activity(
    trip_id: str, command: ActivityCreate, session: Session = Depends(get_db)
):
    return service.itinerary_payload(service.add_activity(session, trip_id, command))


@router.patch("/activities/{activity_id}", response_model=ItineraryRead)
def update_activity(
    activity_id: str, command: ActivityUpdate, session: Session = Depends(get_db)
):
    return service.itinerary_payload(
        service.update_activity(session, activity_id, command)
    )


@router.delete("/activities/{activity_id}", response_model=ItineraryRead)
def delete_activity(
    activity_id: str,
    version: int = Query(ge=1),
    itinerary_version: int = Query(ge=1),
    session: Session = Depends(get_db),
):
    return service.itinerary_payload(
        service.delete_activity(session, activity_id, version, itinerary_version)
    )


@router.put("/trips/{trip_id}/activities/order", response_model=ItineraryRead)
def reorder_activities(
    trip_id: str, command: ActivityOrder, session: Session = Depends(get_db)
):
    return service.itinerary_payload(
        service.reorder_activities(session, trip_id, command)
    )
