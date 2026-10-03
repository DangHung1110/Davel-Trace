"""Trip schemas (T007-foundation, lane C). User + TripRequest per data-model.md."""

from __future__ import annotations

from pydantic import BaseModel, Field


class User(BaseModel):
    user_id: str = "u1"
    lang: str = "vi"
    party_type: str = "solo"
    trip_purpose: str = "leisure"
    spending_level: int = Field(default=2, ge=1, le=3)
    pace: int = Field(default=2, ge=1, le=3)
    fitness: int = Field(default=2, ge=1, le=3)
    food_prefs: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)


class Origin(BaseModel):
    lat: float
    lon: float
    label: str = ""


class TripRequest(BaseModel):
    trip_id: str = "t1"
    user_id: str = "u1"
    origin: Origin | None = None
    city: str = "da-nang"
    date: str = ""
    start_time: str = "07:00"
    end_time: str = "18:00"
    days: int = Field(default=1, ge=1, le=2)
    travelers: int = Field(default=2, ge=1)
    budget: int = Field(default=3000000, ge=0)
    transport: list[str] = Field(default_factory=lambda: ["motorbike"])
    must_visit: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    food_prefs: list[str] = Field(default_factory=list)
    order_prefs: list[list[str]] = Field(default_factory=list)
