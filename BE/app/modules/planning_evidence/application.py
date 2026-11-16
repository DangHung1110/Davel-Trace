"""Planning-evidence ports and transaction-owning application service."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol


class PlanningEvidenceRepository(Protocol):
    def save_acceptance(self, **values) -> dict: ...
    def get_acceptance(self, acceptance_id: str) -> dict | None: ...
    def list_acceptances(
        self, trip_id: str | None = None, limit: int = 50
    ) -> list[dict]: ...
    def count_acceptances(self) -> int: ...
    def save_shadow(self, observation: dict) -> dict: ...
    def list_shadows(self, limit: int = 1000) -> list[dict]: ...


RepositoryContext = Callable[[], AbstractContextManager[PlanningEvidenceRepository]]


class PlanningEvidenceService:
    def __init__(
        self,
        repository_context: RepositoryContext,
    ) -> None:
        self._repository_context = repository_context

    def _read(self, operation):
        with self._repository_context() as repository:
            return operation(repository)

    def _write(self, operation):
        with self._repository_context() as repository:
            return operation(repository)

    def save_acceptance(self, **values) -> dict:
        return self._write(lambda repository: repository.save_acceptance(**values))

    def get_acceptance(self, acceptance_id: str) -> dict | None:
        return self._read(lambda repository: repository.get_acceptance(acceptance_id))

    def list_acceptances(
        self, trip_id: str | None = None, limit: int = 50
    ) -> list[dict]:
        return self._read(
            lambda repository: repository.list_acceptances(trip_id, limit)
        )

    def count_acceptances(self) -> int:
        return self._read(lambda repository: repository.count_acceptances())

    def save_shadow(self, observation: dict) -> dict:
        return self._write(lambda repository: repository.save_shadow(observation))

    def list_shadows(self, limit: int = 1000) -> list[dict]:
        return self._read(lambda repository: repository.list_shadows(limit))
