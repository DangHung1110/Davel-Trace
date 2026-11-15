"""Trip schemas (T007-foundation, lane C). User + TripRequest per data-model.md.

Onboarding profile (shared BE/FE contract, catalog freeze): `TripRequest.profile`
is a plain dict carrying the keys below. It is validated/normalized through
`TripProfile` so a partial payload gets neutral defaults and out-of-range
values are rejected (422 at the API edge) instead of silently ignored:

party_type, trip_purpose, spending_level(1-3), pace(1-3), fitness(1-3),
food_prefs[], allergy[], activities[], outdoor_bias(-1..1), accessibility[],
must_avoid[], transport[].

Neutral defaults: spending/pace/fitness = 2, outdoor_bias = 0.0, lists empty.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TripProfile(BaseModel):
    """Onboarding answer set; the hard pre-filter + day-template inputs."""

    party_type: str = "solo"
    trip_purpose: str = "leisure"
    spending_level: int = Field(default=2, ge=1, le=3)
    pace: int = Field(default=2, ge=1, le=3)
    fitness: int = Field(default=2, ge=1, le=3)
    food_prefs: list[str] = Field(default_factory=list)
    allergy: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    outdoor_bias: float = Field(default=0.0, ge=-1.0, le=1.0)
    accessibility: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    transport: list[str] = Field(default_factory=list)


class User(BaseModel):
    user_id: str = "u1"
    lang: str = "vi"
    party_type: str = "solo"
    trip_purpose: str = "leisure"
    spending_level: int = Field(default=2, ge=1, le=3)
    pace: int = Field(default=2, ge=1, le=3)
    fitness: int = Field(default=2, ge=1, le=3)
    food_prefs: list[str] = Field(default_factory=list)
    allergy: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    outdoor_bias: float = Field(default=0.0, ge=-1.0, le=1.0)
    accessibility: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    transport: list[str] = Field(default_factory=list)


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
    # Catalog-freeze onboarding profile; plain dict on the wire, validated here.
    # The default is the neutral profile (levels 2, bias 0, empty lists), so a
    # client that omits `profile` still sees the exact same key set it can send.
    profile: dict = Field(default_factory=lambda: TripProfile().model_dump())

    @field_validator("profile", mode="before")
    @classmethod
    def _coerce_profile(cls, value):
        """`null` behaves like omitting the profile (neutral defaults)."""
        return {} if value is None else value

    @field_validator("profile", mode="after")
    @classmethod
    def _validate_profile(cls, value: dict) -> dict:
        """Normalize through TripProfile: defaults filled, ranges enforced."""
        if not isinstance(value, dict):
            raise ValueError("profile phai la object")
        return TripProfile(**value).model_dump()
