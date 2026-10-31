"""SQLAlchemy planning-evidence repository; commits belong to the application."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from BE.app.db.models import AcceptanceRecordModel, ShadowObservationModel
from BE.app.services.acceptance_store import AcceptanceStore
from BE.app.modules.planning_evidence.application import PlanningEvidenceService


def _uuid(value: str | UUID | None) -> UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _acceptance_dict(row: AcceptanceRecordModel) -> dict:
    return {
        "acceptance_id": str(row.acceptance_id),
        "idempotency_key": row.idempotency_key,
        "itinerary_id": row.itinerary_id,
        "trip_id": row.trip_id,
        "parent_acceptance_id": (
            str(row.parent_acceptance_id) if row.parent_acceptance_id else None
        ),
        "selected_at": _iso(row.selected_at),
        "schema_version": row.schema_version,
        "data_version": row.data_version,
        "request": row.request_payload,
        "plan": row.plan_payload,
        "gate": row.gate_payload,
        "deterministic_rank": row.deterministic_rank,
        "deterministic_score": row.deterministic_score,
        "shadow_observation_id": (
            str(row.shadow_observation_id) if row.shadow_observation_id else None
        ),
    }


def _shadow_dict(row: ShadowObservationModel) -> dict:
    return {
        "observation_id": str(row.observation_id),
        "trip_id": row.trip_id,
        "created_at": _iso(row.created_at),
        "data_version": row.data_version,
        "candidate_ids": row.candidate_ids,
        "forward": row.forward_result,
        "reverse": row.reverse_result,
        "consensus": row.consensus_result,
        "deterministic_top_id": row.deterministic_top_id,
        "shadow_top_id": row.shadow_top_id,
        "swap_consistent": row.swap_consistent,
        "length_correlation": row.length_correlation,
        "veto_count": row.veto_count,
        "status": row.status,
        "latency_ms": row.latency_ms,
    }


class PostgresPlanningEvidenceRepository:
    """Works with PostgreSQL in production and SQLite only in isolated tests."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_acceptance(self, **values) -> dict:
        key = str(values.get("idempotency_key") or "").strip()
        if not 8 <= len(key) <= 128:
            raise ValueError("idempotency_key phai dai 8-128 ky tu")
        existing = self.session.scalar(
            select(AcceptanceRecordModel).where(
                AcceptanceRecordModel.idempotency_key == key
            )
        )
        if existing is not None:
            return _acceptance_dict(existing)
        row = AcceptanceRecordModel(
            acceptance_id=_uuid(values.get("acceptance_id")) or uuid4(),
            idempotency_key=key,
            itinerary_id=values["itinerary_id"],
            trip_id=values["trip_id"],
            parent_acceptance_id=_uuid(values.get("parent_acceptance_id")),
            selected_at=values.get("selected_at") or datetime.now(timezone.utc),
            schema_version=int(values.get("schema_version") or 1),
            data_version=values["data_version"],
            request_payload=values["request"],
            plan_payload=values["plan"],
            gate_payload=values["gate"],
            deterministic_rank=values.get("deterministic_rank"),
            deterministic_score=values.get("deterministic_score"),
            shadow_observation_id=_uuid(values.get("shadow_observation_id")),
        )
        self.session.add(row)
        self.session.flush()
        return _acceptance_dict(row)

    def get_acceptance(self, acceptance_id: str) -> dict | None:
        try:
            key = UUID(str(acceptance_id))
        except ValueError:
            return None
        row = self.session.get(AcceptanceRecordModel, key)
        return _acceptance_dict(row) if row else None

    def list_acceptances(
        self, trip_id: str | None = None, limit: int = 50
    ) -> list[dict]:
        query = select(AcceptanceRecordModel)
        if trip_id:
            query = query.where(AcceptanceRecordModel.trip_id == trip_id)
        query = query.order_by(
            AcceptanceRecordModel.selected_at.desc(),
            AcceptanceRecordModel.acceptance_id.desc(),
        ).limit(max(1, min(200, int(limit))))
        return [_acceptance_dict(row) for row in self.session.scalars(query)]

    def count_acceptances(self) -> int:
        return int(self.session.scalar(select(func.count(AcceptanceRecordModel.acceptance_id))) or 0)

    def save_shadow(self, observation: dict) -> dict:
        row = ShadowObservationModel(
            observation_id=_uuid(observation.get("observation_id")) or uuid4(),
            trip_id=str(observation.get("trip_id") or ""),
            created_at=observation.get("created_at") or datetime.now(timezone.utc),
            data_version=str(observation.get("data_version") or ""),
            candidate_ids=list(observation.get("candidate_ids") or []),
            forward_result=dict(observation.get("forward") or {}),
            reverse_result=dict(observation.get("reverse") or {}),
            consensus_result=dict(observation.get("consensus") or {}),
            deterministic_top_id=observation.get("deterministic_top_id"),
            shadow_top_id=observation.get("shadow_top_id"),
            swap_consistent=bool(observation.get("swap_consistent")),
            length_correlation=observation.get("length_correlation"),
            veto_count=int(observation.get("veto_count") or 0),
            status=str(observation.get("status") or "skipped"),
            latency_ms=observation.get("latency_ms"),
        )
        self.session.add(row)
        self.session.flush()
        return _shadow_dict(row)

    def list_shadows(self, limit: int = 1000) -> list[dict]:
        query = (
            select(ShadowObservationModel)
            .order_by(
                ShadowObservationModel.created_at.desc(),
                ShadowObservationModel.observation_id.desc(),
            )
            .limit(max(1, min(5000, int(limit))))
        )
        return [_shadow_dict(row) for row in self.session.scalars(query)]


class LegacyPlanningEvidenceAdapter:
    """Temporary demo/test bridge; never selected in production mode."""

    owner = "platform-foundation"
    removal_condition = (
        "Remove after every runtime caller uses PostgreSQL and the explicit "
        "SQLite importer is verified."
    )

    def __init__(self, path: str) -> None:
        self._store = AcceptanceStore(path)

    def save_acceptance(self, **values) -> dict:
        return self._store.save_acceptance(**values)

    def get_acceptance(self, acceptance_id: str) -> dict | None:
        return self._store.get_acceptance(acceptance_id)

    def list_acceptances(
        self, trip_id: str | None = None, limit: int = 50
    ) -> list[dict]:
        return self._store.list_acceptances(trip_id, limit)

    def count_acceptances(self) -> int:
        return self._store.count_acceptances()

    def save_shadow(self, observation: dict) -> dict:
        return self._store.save_shadow(observation)

    def list_shadows(self, limit: int = 1000) -> list[dict]:
        return self._store.list_shadows(limit)


@contextmanager
def postgres_repository_context(session_factory: sessionmaker[Session]):
    with session_factory() as session:
        with session.begin():
            yield PostgresPlanningEvidenceRepository(session)


def create_postgres_planning_evidence_service(
    session_factory: sessionmaker[Session],
) -> PlanningEvidenceService:
    return PlanningEvidenceService(
        lambda: postgres_repository_context(session_factory)
    )
