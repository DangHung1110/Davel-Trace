from __future__ import annotations

from pydantic import BaseModel, Field


class PoiSummary(BaseModel):
    poi_id: str
    name: str
    type: str
    lat: float
    lon: float
    verified: bool
    rating: float | None = None
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    fetched_at: str = ""


class PoiList(BaseModel):
    items: list[PoiSummary]
    snapshot: str
    fetched_at: str
