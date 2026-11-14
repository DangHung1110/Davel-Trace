"""Authenticated HTTP contract for durable itinerary lifecycle."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import time

from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.planning_lifecycle.service import PlanningLifecycleService


router = APIRouter(tags=["planning-lifecycle"])


class ConstraintOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicative_budget: float | None = Field(default=None, ge=0)
    traveler_count: int | None = Field(default=None, ge=1, le=100)
    preferred_transport: str | None = Field(default=None, max_length=32)
    day_start: str | None = None
    day_end: str | None = None
    must_visit: list[str] = Field(default_factory=list, max_length=20)
    avoid: list[str] = Field(default_factory=list, max_length=50)
    activities: list[str] = Field(default_factory=list, max_length=20)
    food_preferences: list[str] = Field(default_factory=list, max_length=20)
    accessibility: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_bounds(self):
        for value in (self.day_start, self.day_end):
            if value is not None:
                time.fromisoformat(value)
        if self.day_start and self.day_end:
            if time.fromisoformat(self.day_end) <= time.fromisoformat(self.day_start):
                raise ValueError("day_end must follow day_start")
        return self


class PlanningRequestBody(BaseModel):
    target_count: int = Field(default=5, ge=1, le=5)
    constraint_overrides: ConstraintOverrides = Field(default_factory=ConstraintOverrides)


class ReplanBody(BaseModel):
    source_version_id: UUID
    completed_activity_ids: list[str] = Field(default_factory=list)
    skipped_activity_ids: list[str] = Field(default_factory=list)
    remaining_from: str | None = None
    unavailable_poi_ids: list[str] = Field(default_factory=list)
    changed_constraints: dict = Field(default_factory=dict)
    target_count: int = Field(default=5, ge=1, le=5)


def _key(value: str | None) -> str:
    return value or ""


@router.post("/v1/trips/{trip_id}/planning-requests", status_code=201)
def create_request(
    trip_id: UUID,
    body: PlanningRequestBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current: Principal = Depends(current_principal),
):
    return PlanningLifecycleService().create_planning_request(
        current,
        trip_id,
        _key(idempotency_key),
        target_count=body.target_count,
        constraint_overrides=body.constraint_overrides.model_dump(exclude_none=True),
    )


@router.get("/v1/planning-requests/{request_id}")
def get_request(
    request_id: UUID,
    current: Principal = Depends(current_principal),
):
    return PlanningLifecycleService().get_request(current, request_id)


@router.post("/v1/itinerary-alternatives/{alternative_id}/accept")
def accept_alternative(
    alternative_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current: Principal = Depends(current_principal),
):
    return PlanningLifecycleService().accept(
        current, alternative_id, _key(idempotency_key)
    )


@router.get("/v1/trips/{trip_id}/itinerary-versions")
def list_versions(
    trip_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current: Principal = Depends(current_principal),
):
    return PlanningLifecycleService().list_versions(
        current, trip_id, limit=limit, offset=offset
    )


@router.get("/v1/itinerary-versions/{version_id}")
def get_version(
    version_id: UUID,
    current: Principal = Depends(current_principal),
):
    return PlanningLifecycleService().get_version(current, version_id)


@router.post("/v1/itinerary-versions/{version_id}/activate")
def activate_version(
    version_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current: Principal = Depends(current_principal),
):
    return PlanningLifecycleService().activate(
        current, version_id, _key(idempotency_key)
    )


@router.post("/v1/trips/{trip_id}/replans", status_code=201)
def replan(
    trip_id: UUID,
    body: ReplanBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current: Principal = Depends(current_principal),
):
    return PlanningLifecycleService().replan(
        current, trip_id, _key(idempotency_key), body.model_dump(mode="json")
    )
