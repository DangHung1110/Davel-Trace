"""Domain values for accepted-plan and shadow evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AcceptanceInput:
    idempotency_key: str
    itinerary_id: str
    trip_id: str
    data_version: str
    request: dict[str, Any]
    plan: dict[str, Any]
    gate: dict[str, Any]


@dataclass(frozen=True)
class EvidenceCounts:
    acceptances: int
    shadows: int
