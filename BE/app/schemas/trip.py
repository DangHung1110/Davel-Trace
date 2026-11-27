"""Trip schemas (T007-foundation, lane C). User + TripRequest per data-model.md.

Onboarding profile (shared BE/FE contract, catalog freeze): `TripRequest.profile`
is a plain dict carrying the keys below. It is validated/normalized through
`TripProfile` so a partial payload gets neutral defaults and out-of-range
values are rejected (422 at the API edge) instead of silently ignored:

party_type, trip_purpose, spending_level(1-3), pace(1-3), fitness(1-3),
food_prefs[], allergy[], activities[], outdoor_bias(-1..1), accessibility[],
must_avoid[], transport[].

Neutral defaults: spending/pace/fitness = 2, outdoor_bias = 0.0, lists empty.

`TripRequest.areas` names the planning zones the traveller wants to stay in (the
`zone` of every danang-v2 POI). Empty means anywhere: the plan is unchanged.

`InternalTripRequest` is the request the server builds for the app's replan: a
TripRequest plus what the stops already done paid (`paid_access`). A client cannot
send it (see the section at the end).
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator, model_validator

# The planning zones of danang-v2 (`zone` of a POI, BE/ml/data/v2_rules.ZONES).
Area = Literal["trung_tam", "son_tra_my_khe", "ngu_hanh_son", "hoi_an",
               "hai_van_lien_chieu", "ba_na_tay"]
AREA_CODES: tuple[str, ...] = get_args(Area)


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


class Origin(BaseModel):
    """Where each day starts: the traveller's base or the stop they are at.

    `poi_id` names a place of the snapshot (a lodging, or the last stop on a replan);
    only a place with a matrix row moves the plan, because every leg must come from
    the matrix (gate B3, no haversine). `lat`/`lon` alone are kept for display.
    """

    lat: float | None = None
    lon: float | None = None
    label: str = ""
    poi_id: str | None = None

    @model_validator(mode="after")
    def _anchored(self) -> "Origin":
        if self.poi_id is None and (self.lat is None or self.lon is None):
            raise ValueError("origin can poi_id hoac ca lat va lon")
        return self


class Resume(BaseModel):
    """A replan in the middle of the first day of a longer trip.

    That day starts at `start_time` from `origin` (where the traveller is now; None is
    the trip's `origin`). The days after it start at the trip's `start_time` from the
    trip's `origin`, as every day of a plan does. On a one-day trip it simply is the
    day's `start_time` and `origin`.
    """

    start_time: str
    origin: Origin | None = None


class TripRequest(BaseModel):
    trip_id: str = "t1"
    user_id: str = "u1"
    origin: Origin | None = None
    # A replan in the middle of the first day (see Resume); None: every day alike.
    resume: Resume | None = None
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
    # Zones the plan stays in (AREA_CODES); a must_visit outside them is still kept.
    areas: list[Area] = Field(default_factory=list)
    # Catalog-freeze onboarding profile; plain dict on the wire, validated here.
    # The default is the neutral profile (levels 2, bias 0, empty lists), so a
    # client that omits `profile` still sees the exact same key set it can send.
    profile: dict = Field(default_factory=lambda: TripProfile().model_dump())

    @model_validator(mode="after")
    def _one_day_resumes_at_its_start(self) -> "TripRequest":
        """A one-day trip has no later day: `resume` is its start and its origin."""
        if self.resume is not None and self.days == 1:
            self.start_time = self.resume.start_time
            self.origin = self.resume.origin or self.origin
            self.resume = None
        return self

    @field_validator("areas", mode="before")
    @classmethod
    def _coerce_areas(cls, value):
        """`null` is no area, like omitting the field."""
        return [] if value is None else value

    @field_validator("areas", mode="after")
    @classmethod
    def _unique_areas(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

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


# --------------------------------------------------------------------------
# What only the server puts in a plan request
# --------------------------------------------------------------------------
# The app's replan (planning_lifecycle) knows which stops are done, so it knows what
# they already paid: a summit stop bought the Sun World ticket (good for 3 days), the
# island the cano of that day. These fields carry it to the planner as
# `paid_access` (BE.common.PAID_ACCESS), which multiday and /v1/replan already use.
# They are not part of the public contract: POST /v1/itinerary reads its body as
# TripRequest, which ignores them, and the API schema does not show them. The
# planner reads them from `model_dump()` of the request it is handed.


class InternalResume(Resume):
    """`Resume` plus what the stops done earlier that day paid for the rest of it
    (`paid_access`: the cano of the island the traveller is on). The days after
    the first pay it again."""

    paid_access: list[str] = Field(default_factory=list)


class InternalTripRequest(TripRequest):
    """A TripRequest built by the server: `paid_access` is what the trip already paid
    (a ticket bought by a stop done, a parent visited), not charged again on any day."""

    resume: InternalResume | None = None
    paid_access: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_day_resumes_at_its_start(self) -> "InternalTripRequest":
        """A one-day trip has no later day: what its first day already paid is the
        trip's, then `resume` folds into its start and origin (TripRequest)."""
        if self.resume is not None and self.days == 1:
            self.paid_access = sorted({*self.paid_access, *self.resume.paid_access})
        return TripRequest._one_day_resumes_at_its_start(self)
