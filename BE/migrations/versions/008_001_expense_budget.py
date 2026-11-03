"""expense and budget management

Revision ID: 008_001
Revises: 007_001
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008_001"
down_revision = "007_001"
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "budget_revisions",
        sa.Column("revision_id", sa.Uuid(), primary_key=True),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_amount", sa.Numeric(14, 2)),
        sa.Column("new_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("new_amount >= 0", name="ck_budget_revisions_budget_revision_amount_non_negative"),
        sa.CheckConstraint("currency = 'VND'", name="ck_budget_revisions_budget_revision_currency_vnd"),
    )
    op.create_index("ix_budget_revisions_trip_changed", "budget_revisions", ["trip_id", "changed_at"])
    op.create_table(
        "expense_entries",
        sa.Column("expense_id", sa.Uuid(), primary_key=True),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_id", sa.Uuid(), sa.ForeignKey("trip_days.day_id", ondelete="SET NULL")),
        sa.Column("activity_id", sa.Uuid(), sa.ForeignKey("trip_activities.activity_id", ondelete="SET NULL")),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("spent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(2000), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_expense_entries_expense_amount_positive"),
        sa.CheckConstraint("currency = 'VND'", name="ck_expense_entries_expense_currency_vnd"),
        sa.CheckConstraint("category IN ('food','ticket','transport','accommodation','shopping','other')", name="ck_expense_entries_expense_category_valid"),
        sa.CheckConstraint("version > 0", name="ck_expense_entries_expense_version_positive"),
    )
    op.create_index("ix_expense_entries_trip_spent", "expense_entries", ["trip_id", "spent_at", "expense_id"])
    op.create_index("ix_expense_entries_trip_category", "expense_entries", ["trip_id", "category"])
    op.create_table(
        "expense_audit_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("expense_id", sa.Uuid()),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("before_payload", JSON_VALUE),
        sa.Column("after_payload", JSON_VALUE),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_expense_audit_trip_occurred", "expense_audit_events", ["trip_id", "occurred_at"])


def downgrade() -> None:
    op.drop_table("expense_audit_events")
    op.drop_table("expense_entries")
    op.drop_table("budget_revisions")
