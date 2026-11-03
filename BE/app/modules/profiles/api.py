"""Profile HTTP routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Literal

from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.profiles.service import ProfileService

router = APIRouter(tags=["profiles"])


class ProfileBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    party_type: Literal["solo", "couple", "family", "friends"] = "solo"
    trip_purpose: Literal["leisure", "discovery", "food", "business"] = "leisure"
    pace: int = Field(default=2, ge=1, le=3)
    fitness: int = Field(default=2, ge=1, le=3)
    spending_style: Literal["saver", "balanced", "comfort"] = "balanced"
    spending_level: int | None = Field(default=None, ge=1, le=3)
    food_preferences: list[str] = Field(default_factory=list)
    preferred_activities: list[str] = Field(default_factory=list)
    usual_transport: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    accessibility_needs: list[str] = Field(default_factory=list)
    expected_version: int | None = None


class ResetBody(BaseModel):
    expected_version: int = Field(ge=1)


@router.get("/v1/profile")
def get_profile(current: Principal = Depends(current_principal)):
    return ProfileService().read(current)


@router.put("/v1/profile")
def put_profile(body: ProfileBody, current: Principal = Depends(current_principal)):
    payload = body.model_dump(exclude={"expected_version"})
    level = payload.pop("spending_level", None)
    if level is not None:
        payload["spending_style"] = {1: "saver", 2: "balanced", 3: "comfort"}[level]
    return ProfileService().save(current, payload, body.expected_version)


@router.post("/v1/profile/reset")
def reset_profile(body: ResetBody, current: Principal = Depends(current_principal)):
    return ProfileService().reset(current, body.expected_version)
