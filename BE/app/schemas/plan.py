"""Plan schemas (T007-plan, lane B). RouteSegment, Activity, Itinerary.

Per data-model.md: ordered activities + segments, totals, constraint
status, version++ on every replan (FR-047). Consumed by optimizer T017,
validator T018, profiles T032. NOTE for lane C: wire re-export in
schemas/models.py when merging (do NOT import poi/eval here).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ActivityStatus = Literal["planned", "done", "cancelled", "replaced"]


class RouteSegment(BaseModel):
    from_id: str
    to_id: str
    mode: str = "motorbike"
    km: float = Field(ge=0)
    minutes: int = Field(ge=0)
    source: Literal["osrm", "cache"] = "cache"
    confidence: str = "medium"
    at: str = ""


class Activity(BaseModel):
    poi_id: str
    kind: str = "visit"
    start: str
    end: str
    intensity: int = Field(default=2, ge=1, le=3)
    visit_min: int = Field(ge=0)
    buffer_min: int = Field(default=0, ge=0)
    status: ActivityStatus = "planned"


class Explanation(BaseModel):
    claim: str
    evidence: str = ""
    inference: str = ""
    source: str = ""


class Itinerary(BaseModel):
    itinerary_id: str
    trip_id: str = "t1"
    version: int = Field(default=1, ge=1)
    activities: list[Activity] = Field(min_length=1)
    segments: list[RouteSegment] = Field(default_factory=list)
    total_cost: int = Field(default=0, ge=0)
    total_km: float = Field(default=0.0, ge=0)
    total_min: int = Field(default=0, ge=0)
    constraint_status: dict = Field(default_factory=dict)
    preference_score: float = 0.0
    explanation: list[Explanation] = Field(default_factory=list)
    created_at: str = ""

    @model_validator(mode="after")
    def _segments_match(self) -> "Itinerary":
        assert len(self.segments) in (0, len(self.activities) - 1), \
            "segments must be empty or one per transition"
        return self
