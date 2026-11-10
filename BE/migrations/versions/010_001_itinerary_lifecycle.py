"""durable itinerary lifecycle

Revision ID: 010_001
Revises: 008_001
Create Date: 2026-11-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "010_001"
down_revision = "008_001"
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "planning_requests",
        sa.Column("request_id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.trip_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_kind", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("trip_version", sa.Integer(), nullable=False),
        sa.Column("data_version", sa.String(128), nullable=False),
        sa.Column("input_payload", JSON_VALUE, nullable=False),
        sa.Column("remaining_context", JSON_VALUE, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("returned_count", sa.Integer(), nullable=False),
        sa.Column("shortage_reason", sa.String(64)),
        sa.Column("failure_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("account_id", "request_kind", "idempotency_key", name="uq_planning_request_owner_kind_key"),
        sa.CheckConstraint("request_kind IN ('plan','replan')", name="ck_planning_requests_planning_request_kind_valid"),
        sa.CheckConstraint("status IN ('running','completed','failed')", name="ck_planning_requests_planning_request_status_valid"),
        sa.CheckConstraint("target_count BETWEEN 1 AND 5 AND returned_count BETWEEN 0 AND 5", name="ck_planning_requests_planning_request_counts_valid"),
    )
    op.create_index("ix_planning_requests_account_id", "planning_requests", ["account_id"])
    op.create_index("ix_planning_requests_trip_id", "planning_requests", ["trip_id"])
    op.create_index("ix_planning_requests_trip_created", "planning_requests", ["trip_id", "created_at"])

    op.create_table(
        "itinerary_alternatives",
        sa.Column("alternative_id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("planning_requests.request_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.trip_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("profile", sa.String(32), nullable=False),
        sa.Column("plan_payload", JSON_VALUE, nullable=False),
        sa.Column("gate_payload", JSON_VALUE, nullable=False),
        sa.Column("deterministic_rank", sa.Integer(), nullable=False),
        sa.Column("deterministic_score", sa.Float()),
        sa.Column("data_version", sa.String(128), nullable=False),
        sa.Column("selectability_state", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_id", "fingerprint", name="uq_itinerary_alternative_request_fingerprint"),
        sa.CheckConstraint("selectability_state IN ('current','selected','superseded','invalidated')", name="ck_itinerary_alternatives_itinerary_alternative_state_valid"),
        sa.CheckConstraint("deterministic_rank BETWEEN 1 AND 5", name="ck_itinerary_alternatives_itinerary_alternative_rank_valid"),
    )
    op.create_index("ix_itinerary_alternatives_request_id", "itinerary_alternatives", ["request_id"])
    op.create_index("ix_itinerary_alternatives_trip_created", "itinerary_alternatives", ["trip_id", "created_at"])

    op.create_table(
        "itinerary_versions",
        sa.Column("version_id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.trip_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("alternative_id", sa.Uuid(), sa.ForeignKey("itinerary_alternatives.alternative_id", ondelete="RESTRICT"), unique=True),
        sa.Column("parent_version_id", sa.Uuid(), sa.ForeignKey("itinerary_versions.version_id", ondelete="RESTRICT")),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("plan_payload", JSON_VALUE, nullable=False),
        sa.Column("gate_payload", JSON_VALUE, nullable=False),
        sa.Column("request_payload", JSON_VALUE, nullable=False),
        sa.Column("data_version", sa.String(128), nullable=False),
        sa.Column("deterministic_rank", sa.Integer()),
        sa.Column("deterministic_score", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trip_id", "ordinal", name="uq_itinerary_version_trip_ordinal"),
        sa.CheckConstraint("ordinal > 0", name="ck_itinerary_versions_itinerary_version_ordinal_positive"),
    )
    op.create_index("ix_itinerary_versions_trip_created", "itinerary_versions", ["trip_id", "created_at"])
    op.create_foreign_key(
        "fk_planning_requests_source_version_id_itinerary_versions",
        "planning_requests", "itinerary_versions",
        ["source_version_id"], ["version_id"], ondelete="RESTRICT",
    )

    op.create_table(
        "active_itinerary_versions",
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.trip_id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("itinerary_versions.version_id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_active_itinerary_versions_active_itinerary_version_revision_positive"),
    )

    op.create_table(
        "itinerary_version_transitions",
        sa.Column("transition_id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.trip_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("from_version_id", sa.Uuid(), sa.ForeignKey("itinerary_versions.version_id", ondelete="RESTRICT")),
        sa.Column("to_version_id", sa.Uuid(), sa.ForeignKey("itinerary_versions.version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.UniqueConstraint("account_id", "reason", "idempotency_key", name="uq_itinerary_transition_owner_reason_key"),
        sa.CheckConstraint("reason IN ('accept','replan_accept','reactivate')", name="ck_itinerary_version_transitions_itinerary_transition_reason_valid"),
    )
    op.create_index("ix_itinerary_transitions_trip_occurred", "itinerary_version_transitions", ["trip_id", "occurred_at"])

    op.add_column("acceptance_records", sa.Column("account_id", sa.Uuid(), nullable=True))
    op.add_column("acceptance_records", sa.Column("request_id", sa.Uuid(), nullable=True))
    op.add_column("acceptance_records", sa.Column("alternative_id", sa.Uuid(), nullable=True))
    op.add_column("acceptance_records", sa.Column("itinerary_version_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_acceptance_records_account_id_accounts", "acceptance_records", "accounts", ["account_id"], ["account_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_acceptance_records_request_id_planning_requests", "acceptance_records", "planning_requests", ["request_id"], ["request_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_acceptance_records_alternative_id_itinerary_alternatives", "acceptance_records", "itinerary_alternatives", ["alternative_id"], ["alternative_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_acceptance_records_itinerary_version_id_itinerary_versions", "acceptance_records", "itinerary_versions", ["itinerary_version_id"], ["version_id"], ondelete="RESTRICT")
    op.create_index("ix_acceptance_records_account_id", "acceptance_records", ["account_id"])
    op.create_unique_constraint("uq_acceptance_records_itinerary_version_id", "acceptance_records", ["itinerary_version_id"])


def downgrade() -> None:
    op.drop_constraint("uq_acceptance_records_itinerary_version_id", "acceptance_records", type_="unique")
    op.drop_index("ix_acceptance_records_account_id", table_name="acceptance_records")
    for name in (
        "fk_acceptance_records_itinerary_version_id_itinerary_versions",
        "fk_acceptance_records_alternative_id_itinerary_alternatives",
        "fk_acceptance_records_request_id_planning_requests",
        "fk_acceptance_records_account_id_accounts",
    ):
        op.drop_constraint(name, "acceptance_records", type_="foreignkey")
    for column in ("itinerary_version_id", "alternative_id", "request_id", "account_id"):
        op.drop_column("acceptance_records", column)
    op.drop_table("itinerary_version_transitions")
    op.drop_table("active_itinerary_versions")
    op.drop_constraint(
        "fk_planning_requests_source_version_id_itinerary_versions",
        "planning_requests", type_="foreignkey",
    )
    op.drop_table("itinerary_versions")
    op.drop_table("itinerary_alternatives")
    op.drop_table("planning_requests")
