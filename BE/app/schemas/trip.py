from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from BE.app.schemas.common import OrmModel

TripStatus = Literal["draft", "planned", "active", "done", "cancelled"]


def _validate_trip_range(start: date, end: date, day_start: time, day_end: time) -> None:
    days = (end - start).days
    if days < 0 or days > 1:
        raise ValueError("trip must be one or two calendar days")
    if days == 0 and day_end <= day_start:
        raise ValueError("day_end must be after day_start")


class TripCreate(BaseModel):
    profile_id: str
    title: str = Field(min_length=1, max_length=120)
    city: Literal["da-nang"] = "da-nang"
    start_date: date
    end_date: date
    day_start: time
    day_end: time
    travelers: int = Field(default=1, ge=1, le=50)
    budget_vnd: int = Field(default=0, ge=0)
    transport: str = Field(default="motorbike", min_length=1, max_length=32)

    @field_validator("title", "transport")
    @classmethod
    def trim_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "TripCreate":
        _validate_trip_range(self.start_date, self.end_date, self.day_start, self.day_end)
        return self


class TripUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    day_start: time | None = None
    day_end: time | None = None
    travelers: int | None = Field(default=None, ge=1, le=50)
    budget_vnd: int | None = Field(default=None, ge=0)
    transport: str | None = Field(default=None, min_length=1, max_length=32)
    status: TripStatus | None = None
    version: int = Field(ge=1)

    @field_validator("title", "transport")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class TripRead(OrmModel):
    id: str
    profile_id: str
    title: str
    city: str
    start_date: date
    end_date: date
    day_start: time
    day_end: time
    travelers: int
    budget_vnd: int
    transport: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class TripList(BaseModel):
    items: list[TripRead]


class ActivityCreate(BaseModel):
    poi_id: str | None = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=160)
    notes: str = Field(default="", max_length=1000)
    position: int | None = Field(default=None, ge=0)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start_at: datetime
    end_at: datetime
    category: str = Field(default="visit", min_length=1, max_length=40)
    estimated_cost_vnd: int = Field(default=0, ge=0)
    itinerary_version: int = Field(ge=1)

    @field_validator("title", "category")
    @classmethod
    def trim_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_time(self) -> "ActivityCreate":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class ActivityUpdate(BaseModel):
    poi_id: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    start_at: datetime | None = None
    end_at: datetime | None = None
    category: str | None = Field(default=None, min_length=1, max_length=40)
    estimated_cost_vnd: int | None = Field(default=None, ge=0)
    version: int = Field(ge=1)
    itinerary_version: int = Field(ge=1)


class ActivityRead(OrmModel):
    id: str
    itinerary_id: str
    position: int
    poi_id: str | None
    title: str
    notes: str
    latitude: float
    longitude: float
    start_at: datetime
    end_at: datetime
    category: str
    estimated_cost_vnd: int
    source: str
    version: int
    created_at: datetime
    updated_at: datetime


class OverlapWarning(BaseModel):
    activity_ids: list[str]
    message: str


class ItineraryRead(OrmModel):
    id: str
    trip_id: str
    version: int
    source: str
    status: str
    activities: list[ActivityRead]
    warnings: list[OverlapWarning] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ActivityOrder(BaseModel):
    activity_ids: list[str] = Field(min_length=1)
    itinerary_version: int = Field(ge=1)


class TripDetail(TripRead):
    itinerary: ItineraryRead
    expense_summary: dict
