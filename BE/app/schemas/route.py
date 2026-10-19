from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RoutePreviewRequest(BaseModel):
    trip_id: str
    activity_ids: list[str] = Field(min_length=2, max_length=10)
    mode: Literal["driving", "walking", "cycling"] = "driving"


class RoutePreview(BaseModel):
    source: Literal["osrm", "fallback"]
    is_real_route: bool
    distance_m: int
    duration_s: int
    geometry: list[list[float]]
    warning: str | None = None
