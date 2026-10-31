"""Small in-memory planning-evidence test double."""

from __future__ import annotations

from uuid import uuid4


class InMemoryPlanningEvidenceRepository:
    def __init__(self) -> None:
        self.acceptances: list[dict] = []
        self.shadows: list[dict] = []

    def save_acceptance(self, **values) -> dict:
        for row in self.acceptances:
            if row["idempotency_key"] == values["idempotency_key"]:
                return dict(row)
        row = {"acceptance_id": str(uuid4()), **values}
        self.acceptances.append(row)
        return dict(row)

    def get_acceptance(self, acceptance_id: str) -> dict | None:
        return next(
            (dict(row) for row in self.acceptances if row["acceptance_id"] == acceptance_id),
            None,
        )

    def list_acceptances(self, trip_id=None, limit=50) -> list[dict]:
        rows = self.acceptances
        if trip_id:
            rows = [row for row in rows if row.get("trip_id") == trip_id]
        return [dict(row) for row in rows[-limit:][::-1]]

    def count_acceptances(self) -> int:
        return len(self.acceptances)

    def save_shadow(self, observation: dict) -> dict:
        row = {"observation_id": str(uuid4()), **observation}
        self.shadows.append(row)
        return dict(row)

    def list_shadows(self, limit=1000) -> list[dict]:
        return [dict(row) for row in self.shadows[-limit:][::-1]]
