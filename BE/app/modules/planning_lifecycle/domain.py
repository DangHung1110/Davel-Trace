"""Framework-free lifecycle values and deterministic fingerprints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RequestKind = Literal["plan", "replan"]
RequestStatus = Literal["running", "completed", "failed"]
TransitionReason = Literal["accept", "replan_accept", "reactivate"]


@dataclass(frozen=True)
class PlanningCommand:
    trip_id: str
    idempotency_key: str
    target_count: int = 5
    constraint_overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReplanCommand(PlanningCommand):
    source_version_id: str = ""
    completed_activity_ids: tuple[str, ...] = ()
    skipped_activity_ids: tuple[str, ...] = ()
    remaining_from: str | None = None
    unavailable_poi_ids: tuple[str, ...] = ()
    changed_constraints: dict[str, Any] = field(default_factory=dict)
