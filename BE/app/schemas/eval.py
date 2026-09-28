"""Eval schemas (T007-eval, lane A). EvaluationRecord per data-model.md."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvaluationRecord(BaseModel):
    input: dict = Field(default_factory=dict)
    itinerary_id: str = ""
    baseline: str = ""
    gate: dict = Field(default_factory=dict)
    soft: dict = Field(default_factory=dict)
    recovery: dict = Field(default_factory=dict)
    pairwise_label: int | None = Field(default=None, ge=-1, le=1)
