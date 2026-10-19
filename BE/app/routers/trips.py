from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from BE.app.database import get_db
from BE.app.schemas.trip import TripCreate, TripDetail, TripList, TripRead, TripUpdate
from BE.app.services import expenses as expense_service
from BE.app.services import itineraries as itinerary_service
from BE.app.services import trips as service

router = APIRouter(prefix="/v1/trips", tags=["trips"])


@router.get("", response_model=TripList)
def list_trips(profile_id: str, session: Session = Depends(get_db)):
    return {"items": service.list_trips(session, profile_id)}


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(command: TripCreate, session: Session = Depends(get_db)):
    return service.create_trip(session, command)


@router.get("/{trip_id}", response_model=TripDetail)
def get_trip(trip_id: str, session: Session = Depends(get_db)):
    trip = service.get_trip(session, trip_id, detail=True)
    _, summary = expense_service.list_with_summary(session, trip_id)
    payload = TripRead.model_validate(trip).model_dump(mode="json")
    payload["itinerary"] = itinerary_service.itinerary_payload(trip.itinerary)
    payload["expense_summary"] = summary
    return payload


@router.patch("/{trip_id}", response_model=TripRead)
def update_trip(
    trip_id: str, command: TripUpdate, session: Session = Depends(get_db)
):
    return service.update_trip(session, trip_id, command)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(
    trip_id: str,
    version: int = Query(ge=1),
    confirm: bool = False,
    session: Session = Depends(get_db),
):
    service.delete_trip(session, trip_id, version, confirm)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
