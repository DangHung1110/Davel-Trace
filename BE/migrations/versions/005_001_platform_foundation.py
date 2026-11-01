"""Create platform foundation and planning-evidence tables.

Revision ID: 005_001
Revises: None
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "005_001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shadow_observations",
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_version", sa.String(length=128), nullable=False),
        sa.Column("candidate_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("forward_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reverse_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("consensus_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("deterministic_top_id", sa.String(length=128), nullable=True),
        sa.Column("shadow_top_id", sa.String(length=128), nullable=True),
        sa.Column("swap_consistent", sa.Boolean(), nullable=False),
        sa.Column("length_correlation", sa.Float(), nullable=True),
        sa.Column("veto_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "length_correlation IS NULL OR "
            "(length_correlation >= -1 AND length_correlation <= 1)",
            name="ck_shadow_observations_correlation_range",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_shadow_observations_latency_non_negative",
        ),
        sa.CheckConstraint(
            "status IN ('skipped', 'completed', 'failed')",
            name="ck_shadow_observations_status_valid",
        ),
        sa.CheckConstraint(
            "veto_count >= 0",
            name="ck_shadow_observations_veto_count_non_negative",
        ),
        sa.PrimaryKeyConstraint("observation_id", name="pk_shadow_observations"),
    )
    op.create_index(
        "ix_shadow_status_created",
        "shadow_observations",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_shadow_trip_created",
        "shadow_observations",
        ["trip_id", "created_at", "observation_id"],
    )

    op.create_table(
        "acceptance_records",
        sa.Column("acceptance_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("itinerary_id", sa.String(length=128), nullable=False),
        sa.Column("trip_id", sa.String(length=128), nullable=False),
        sa.Column("parent_acceptance_id", sa.Uuid(), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("data_version", sa.String(length=128), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("plan_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("gate_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("deterministic_rank", sa.Integer(), nullable=True),
        sa.Column("deterministic_score", sa.Float(), nullable=True),
        sa.Column("shadow_observation_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "deterministic_rank IS NULL OR deterministic_rank > 0",
            name="ck_acceptance_records_deterministic_rank_positive",
        ),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 8 AND 128",
            name="ck_acceptance_records_idempotency_key_length",
        ),
        sa.CheckConstraint(
            "schema_version > 0",
            name="ck_acceptance_records_schema_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["parent_acceptance_id"],
            ["acceptance_records.acceptance_id"],
            name="fk_acceptance_records_parent_acceptance_id_acceptance_records",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shadow_observation_id"],
            ["shadow_observations.observation_id"],
            name="fk_acceptance_records_shadow_observation_id_shadow_observations",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("acceptance_id", name="pk_acceptance_records"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_acceptance_records_idempotency_key"
        ),
    )
    op.create_index(
        "ix_acceptance_data_version", "acceptance_records", ["data_version"]
    )
    op.create_index(
        "ix_acceptance_trip_selected",
        "acceptance_records",
        ["trip_id", "selected_at", "acceptance_id"],
    )

    op.create_table(
        "import_runs",
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("acceptance_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("shadow_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "acceptance_count >= 0",
            name="ck_import_runs_acceptance_count_non_negative",
        ),
        sa.CheckConstraint(
            "shadow_count >= 0", name="ck_import_runs_shadow_count_non_negative"
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_import_runs_status_valid",
        ),
        sa.PrimaryKeyConstraint("import_id", name="pk_import_runs"),
        sa.UniqueConstraint(
            "source_kind",
            "source_fingerprint",
            name="uq_import_runs_source_kind",
        ),
    )

    op.create_table(
        "seed_runs",
        sa.Column("seed_run_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_name", sa.String(length=128), nullable=False),
        sa.Column("dataset_version", sa.String(length=64), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "mode IN ('demo', 'test')", name="ck_seed_runs_mode_valid"
        ),
        sa.PrimaryKeyConstraint("seed_run_id", name="pk_seed_runs"),
        sa.UniqueConstraint(
            "dataset_name",
            "dataset_version",
            "checksum",
            "mode",
            name="uq_seed_runs_dataset_name",
        ),
    )


def downgrade() -> None:
    op.drop_table("seed_runs")
    op.drop_table("import_runs")
    op.drop_index("ix_acceptance_trip_selected", table_name="acceptance_records")
    op.drop_index("ix_acceptance_data_version", table_name="acceptance_records")
    op.drop_table("acceptance_records")
    op.drop_index("ix_shadow_trip_created", table_name="shadow_observations")
    op.drop_index("ix_shadow_status_created", table_name="shadow_observations")
    op.drop_table("shadow_observations")
