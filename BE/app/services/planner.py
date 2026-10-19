from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PlannerProposal:
    proposal_id: str
    trip_id: str
    base_itinerary_version: int
    activities: tuple[dict, ...]
    explanation: tuple[str, ...] = ()


class PlannerPort(Protocol):
    """Future AI boundary. No implementation or endpoint is enabled in this MVP."""

    def generate(self, trip: dict, preferences: dict, pois: list[dict]) -> list[PlannerProposal]: ...
