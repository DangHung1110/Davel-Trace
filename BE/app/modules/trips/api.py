"""Trip, day, activity, selection, and lifecycle HTTP routes."""

from datetime import date, time
from decimal import Decimal
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field

from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.trips.service import TripService

router = APIRouter(tags=["trips"])


def require_key(value: str | None) -> str:
    if not value or not 8 <= len(value) <= 128:
        raise IdentityError("VALIDATION_ERROR", "Idempotency-Key phải dài 8-128 ký tự.", 422)
    return value


class TripCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    start_date: date
    end_date: date
    traveler_count: int = Field(ge=1, le=20)
    indicative_budget: Decimal | None = Field(default=None, ge=0)
    preferred_transport: str = "mixed"
    day_start: time
    day_end: time
    notes: str = Field(default="", max_length=2000)
    preference_overrides: dict = Field(default_factory=dict)


class TripUpdateBody(BaseModel):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    traveler_count: int | None = Field(default=None, ge=1, le=20)
    indicative_budget: Decimal | None = Field(default=None, ge=0)
    preferred_transport: str | None = None
    day_start: time | None = None
    day_end: time | None = None
    notes: str | None = Field(default=None, max_length=2000)
    preference_overrides: dict | None = None
    confirm_removed_days: bool = False


class ActiveBody(BaseModel):
    trip_id: UUID | None
    expected_selection_version: int = Field(ge=0)


class VersionBody(BaseModel):
    expected_version: int = Field(ge=1)


class ActivityBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: str = "custom"
    poi_id: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    notes: str = Field(default="", max_length=2000)


class ActivityUpdateBody(BaseModel):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=200)
    kind: str | None = None
    poi_id: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)
    progress_state: Literal["planned", "completed", "skipped"] | None = None


class OrderBody(BaseModel):
    activity_ids: list[str]
    expected_day_version: int = Field(ge=1)


@router.get("/v1/trips")
def list_trips(q: str = Query(default="", max_length=160), state: str | None = None,
               current: Principal = Depends(current_principal)):
    return TripService().list(current, q, state)


@router.post("/v1/trips", status_code=201)
def create_trip(body: TripCreateBody, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                current: Principal = Depends(current_principal)):
    return TripService().create(current, body.model_dump(), require_key(idempotency_key))


@router.put("/v1/trips/active")
def set_active(body: ActiveBody, current: Principal = Depends(current_principal)):
    return TripService().set_active(current, body.trip_id, body.expected_selection_version)


@router.get("/v1/trips/{trip_id}")
def get_trip(trip_id: UUID, current: Principal = Depends(current_principal)):
    return TripService().get(current, trip_id)


@router.patch("/v1/trips/{trip_id}")
def update_trip(trip_id: UUID, body: TripUpdateBody, current: Principal = Depends(current_principal)):
    data = body.model_dump(exclude={"expected_version", "confirm_removed_days"}, exclude_none=True)
    return TripService().update(current, trip_id, data, body.expected_version, body.confirm_removed_days)


@router.post("/v1/trips/{trip_id}/archive")
def archive(trip_id: UUID, body: VersionBody, current: Principal = Depends(current_principal)):
    return TripService().lifecycle(current, trip_id, "archive", body.expected_version)


@router.post("/v1/trips/{trip_id}/restore")
def restore(trip_id: UUID, body: VersionBody, current: Principal = Depends(current_principal)):
    return TripService().lifecycle(current, trip_id, "restore", body.expected_version)


@router.post("/v1/trips/{trip_id}/deletion", status_code=204)
def delete_trip(trip_id: UUID, body: VersionBody, current: Principal = Depends(current_principal)):
    TripService().lifecycle(current, trip_id, "delete", body.expected_version)
    return Response(status_code=204)


@router.post("/v1/trips/{trip_id}/days/{day_id}/activities", status_code=201)
def add_activity(trip_id: UUID, day_id: UUID, body: ActivityBody,
                 idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                 current: Principal = Depends(current_principal)):
    return TripService().add_activity(current, trip_id, day_id, body.model_dump(), require_key(idempotency_key))


@router.patch("/v1/activities/{activity_id}")
def update_activity(activity_id: UUID, body: ActivityUpdateBody, current: Principal = Depends(current_principal)):
    return TripService().update_activity(current, activity_id,
        body.model_dump(exclude={"expected_version"}, exclude_none=True), body.expected_version)


@router.delete("/v1/activities/{activity_id}")
def delete_activity(activity_id: UUID, expected_version: int = Query(ge=1),
                    current: Principal = Depends(current_principal)):
    return TripService().delete_activity(current, activity_id, expected_version)


@router.put("/v1/trips/{trip_id}/days/{day_id}/activities/order")
def reorder(trip_id: UUID, day_id: UUID, body: OrderBody, current: Principal = Depends(current_principal)):
    return TripService().reorder(current, trip_id, day_id, body.activity_ids, body.expected_day_version)
