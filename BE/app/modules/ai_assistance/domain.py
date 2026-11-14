"""Provider-neutral schemas for untrusted model output."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator


class InterpretationDraft(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    day_start: str | None = None
    day_end: str | None = None
    budget: int | None = Field(default=None, ge=0, le=1_000_000_000)
    travelers: int | None = Field(default=None, ge=1, le=100)
    must_visit: list[str] = Field(default_factory=list, max_length=20)
    avoid: list[str] = Field(default_factory=list, max_length=20)
    activities: list[str] = Field(default_factory=list, max_length=20)
    food_preferences: list[str] = Field(default_factory=list, max_length=20)
    accessibility: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    unresolved: list[str] = Field(default_factory=list, max_length=20)

    @field_validator(
        "must_visit", "avoid", "activities", "food_preferences",
        "accessibility", "assumptions", "unresolved", mode="after"
    )
    @classmethod
    def normalize_strings(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))

    @field_validator("day_start", "day_end")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = value.split(":")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ValueError("time must use HH:MM")
        hour, minute = map(int, parts)
        if hour > 23 or minute > 59:
            raise ValueError("time must use HH:MM")
        return f"{hour:02d}:{minute:02d}"

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return date.fromisoformat(value).isoformat()

    @model_validator(mode="after")
    def validate_dates(self) -> "InterpretationDraft":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date precedes start_date")
        if self.day_start and self.day_end and self.day_end <= self.day_start:
            raise ValueError("day_end must be after day_start")
        return self


class ExplanationReason(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    evidence_keys: list[str] = Field(min_length=1, max_length=10)


class ExplanationDraft(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    reasons: list[ExplanationReason] = Field(default_factory=list, max_length=10)


class ShadowDraft(BaseModel):
    ranked_ids: list[str] = Field(min_length=1, max_length=5)
