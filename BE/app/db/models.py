"""Authoritative platform SQLAlchemy models for foundation increment 005."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from BE.app.db.base import Base


JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AcceptanceRecordModel(Base):
    __tablename__ = "acceptance_records"
    __table_args__ = (
        CheckConstraint(
            "length(idempotency_key) BETWEEN 8 AND 128",
            name="idempotency_key_length",
        ),
        CheckConstraint("schema_version > 0", name="schema_version_positive"),
        CheckConstraint(
            "deterministic_rank IS NULL OR deterministic_rank > 0",
            name="deterministic_rank_positive",
        ),
        Index(
            "ix_acceptance_trip_selected",
            "trip_id",
            "selected_at",
            "acceptance_id",
        ),
        Index("ix_acceptance_data_version", "data_version"),
    )

    acceptance_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    itinerary_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trip_id: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_acceptance_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("acceptance_records.acceptance_id", ondelete="RESTRICT"),
        nullable=True,
    )
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    data_version: Mapped[str] = mapped_column(String(128), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False)
    plan_payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False)
    gate_payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False)
    deterministic_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deterministic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    shadow_observation_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shadow_observations.observation_id", ondelete="SET NULL"),
        nullable=True,
    )


class ShadowObservationModel(Base):
    __tablename__ = "shadow_observations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('skipped', 'completed', 'failed')",
            name="status_valid",
        ),
        CheckConstraint("veto_count >= 0", name="veto_count_non_negative"),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="latency_non_negative",
        ),
        CheckConstraint(
            "length_correlation IS NULL OR "
            "(length_correlation >= -1 AND length_correlation <= 1)",
            name="correlation_range",
        ),
        Index(
            "ix_shadow_trip_created",
            "trip_id",
            "created_at",
            "observation_id",
        ),
        Index("ix_shadow_status_created", "status", "created_at"),
    )

    observation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    trip_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    data_version: Mapped[str] = mapped_column(String(128), nullable=False)
    candidate_ids: Mapped[list[str]] = mapped_column(JSON_VALUE, nullable=False)
    forward_result: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False)
    reverse_result: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False)
    consensus_result: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False)
    deterministic_top_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shadow_top_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    swap_consistent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    length_correlation: Mapped[float | None] = mapped_column(Float, nullable=True)
    veto_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ImportRunModel(Base):
    __tablename__ = "import_runs"
    __table_args__ = (
        UniqueConstraint("source_kind", "source_fingerprint"),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="status_valid",
        ),
        CheckConstraint("acceptance_count >= 0", name="acceptance_count_non_negative"),
        CheckConstraint("shadow_count >= 0", name="shadow_count_non_negative"),
    )

    import_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    acceptance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shadow_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))


class SeedRunModel(Base):
    __tablename__ = "seed_runs"
    __table_args__ = (
        UniqueConstraint("dataset_name", "dataset_version", "checksum", "mode"),
        CheckConstraint("mode IN ('demo', 'test')", name="mode_valid"),
    )

    seed_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
