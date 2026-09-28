"""POI schemas (T007-poi, lane A). POI + Restaurant per data-model.md.

Duration semantics (research R8): optimizer schedules with p50, gate
checks p75 buffer, UI shows "~p25-p75 (uoc tinh)" — never as fact.
dur_source vocab: category_rule | llm | review_mined | actual
(+ pending_llm = transient seed state before nac-2 runs).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

DurSource = Literal["category_rule", "llm", "review_mined", "actual", "pending_llm"]
DurConfidence = Literal["low", "medium", "high"]


class VisitMin(BaseModel):
    p25: int = Field(gt=0)
    p50: int = Field(gt=0)
    p75: int = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> "VisitMin":
        assert self.p25 <= self.p50 <= self.p75, "need p25<=p50<=p75"
        return self


class POI(BaseModel):
    poi_id: str
    name: str
    type: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    opening_hours: list[str] = Field(default_factory=list)
    visit_min: VisitMin
    dur_source: DurSource = "category_rule"
    dur_confidence: DurConfidence = "low"
    price_level: int = Field(default=2, ge=1, le=3)
    fee: int = Field(default=0, ge=0)
    rating: float | None = Field(default=None, ge=0, le=5)
    tags: list[str] = Field(default_factory=list)
    intensity: int = Field(default=2, ge=1, le=3)
    ambience: str = ""
    crowd: str = ""
    dietary: list[str] = Field(default_factory=list)
    weather_sensitive: bool = False
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    source: str
    fetched_at: str
    verified: bool


class Restaurant(POI):
    cuisine: list[str] = Field(default_factory=list)
    price_range: str = ""
    reservation: bool = False
    meal_slots: list[str] = Field(default_factory=list)
