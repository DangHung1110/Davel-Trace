from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from BE.app.schemas.common import OrmModel


class ProfileFields(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    language: str = Field(default="vi", min_length=2, max_length=8)
    party_type: str = Field(default="solo", min_length=1, max_length=24)
    trip_purpose: str = Field(default="leisure", min_length=1, max_length=24)
    spending_level: int = Field(default=2, ge=1, le=3)
    pace: int = Field(default=2, ge=1, le=3)
    fitness: int = Field(default=2, ge=1, le=3)
    food_preferences: list[str] = Field(default_factory=list, max_length=30)
    must_avoid: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("display_name", "language", "party_type", "trip_purpose")
    @classmethod
    def trim_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("food_preferences", "must_avoid")
    @classmethod
    def trim_list(cls, values: list[str]) -> list[str]:
        return [item.strip() for item in values if item.strip()]


class ProfileCreate(ProfileFields):
    pass


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    language: str | None = Field(default=None, min_length=2, max_length=8)
    party_type: str | None = Field(default=None, min_length=1, max_length=24)
    trip_purpose: str | None = Field(default=None, min_length=1, max_length=24)
    spending_level: int | None = Field(default=None, ge=1, le=3)
    pace: int | None = Field(default=None, ge=1, le=3)
    fitness: int | None = Field(default=None, ge=1, le=3)
    food_preferences: list[str] | None = Field(default=None, max_length=30)
    must_avoid: list[str] | None = Field(default=None, max_length=30)
    version: int = Field(ge=1)

    @field_validator("display_name", "language", "party_type", "trip_purpose")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ProfileRead(OrmModel):
    id: str
    display_name: str
    language: str
    party_type: str
    trip_purpose: str
    spending_level: int
    pace: int
    fitness: int
    food_preferences: list[str]
    must_avoid: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


class ProfileList(BaseModel):
    items: list[ProfileRead]
    active_profile_id: str | None


class ActiveProfileRead(BaseModel):
    active_profile_id: str | None
