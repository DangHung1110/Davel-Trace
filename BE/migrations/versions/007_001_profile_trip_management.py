"""profile and trip management

Revision ID: 007_001
Revises: 006_001
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007_001"
down_revision = "006_001"
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table("traveler_profiles",
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("party_type", sa.String(32), nullable=False), sa.Column("trip_purpose", sa.String(32), nullable=False),
        sa.Column("pace", sa.Integer(), nullable=False), sa.Column("fitness", sa.Integer(), nullable=False),
        sa.Column("spending_style", sa.String(32), nullable=False),
        sa.Column("food_preferences", JSON_VALUE, nullable=False), sa.Column("preferred_activities", JSON_VALUE, nullable=False),
        sa.Column("usual_transport", JSON_VALUE, nullable=False), sa.Column("must_avoid", JSON_VALUE, nullable=False),
        sa.Column("allergies", JSON_VALUE, nullable=False), sa.Column("accessibility_needs", JSON_VALUE, nullable=False),
        sa.Column("onboarding_complete", sa.Boolean(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_traveler_profiles_traveler_profile_version_positive"))
    op.create_table("trips",
        sa.Column("trip_id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False), sa.Column("destination", sa.String(64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("traveler_count", sa.Integer(), nullable=False), sa.Column("progress_state", sa.String(24), nullable=False),
        sa.Column("lifecycle_state", sa.String(24), nullable=False), sa.Column("review_state", sa.String(24), nullable=False),
        sa.Column("indicative_budget", sa.Numeric(14, 2)), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("preferred_transport", sa.String(32), nullable=False), sa.Column("day_start", sa.Time(), nullable=False), sa.Column("day_end", sa.Time(), nullable=False),
        sa.Column("notes", sa.String(2000), nullable=False), sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_snapshot", JSON_VALUE, nullable=False), sa.Column("preference_overrides", JSON_VALUE, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)), sa.Column("purge_after", sa.DateTime(timezone=True)),
        sa.CheckConstraint("traveler_count BETWEEN 1 AND 20", name="ck_trips_trip_traveler_count_valid"),
        sa.CheckConstraint("end_date >= start_date", name="ck_trips_trip_date_order_valid"),
        sa.CheckConstraint("version > 0", name="ck_trips_trip_version_positive"),
        sa.CheckConstraint("lifecycle_state IN ('available','archived','deleted','purged')", name="ck_trips_trip_lifecycle_valid"))
    op.create_index("ix_trips_account_id", "trips", ["account_id"])
    op.create_index("ix_trips_owner_lifecycle_updated", "trips", ["account_id", "lifecycle_state", "updated_at"])
    op.create_table("trip_days",
        sa.Column("day_id", sa.Uuid(), primary_key=True), sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False), sa.Column("position", sa.Integer(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trip_id", "local_date", name="uq_trip_days_trip_date"),
        sa.UniqueConstraint("trip_id", "position", name="uq_trip_days_trip_position"),
        sa.CheckConstraint("position >= 0", name="ck_trip_days_trip_day_position_non_negative"))
    op.create_index("ix_trip_days_trip_id", "trip_days", ["trip_id"])
    op.create_table("trip_activities",
        sa.Column("activity_id", sa.Uuid(), primary_key=True), sa.Column("day_id", sa.Uuid(), sa.ForeignKey("trip_days.day_id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False), sa.Column("poi_id", sa.String(128)), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("start_time", sa.Time()), sa.Column("end_time", sa.Time()), sa.Column("duration_minutes", sa.Integer()),
        sa.Column("estimated_cost", sa.Numeric(14, 2)), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("progress_state", sa.String(24), nullable=False), sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(2000), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("day_id", "position"), sa.CheckConstraint("position >= 0", name="ck_trip_activities_trip_activity_position_non_negative"),
        sa.CheckConstraint("progress_state IN ('planned','completed','skipped')", name="ck_trip_activities_trip_activity_progress_valid"))
    op.create_index("ix_trip_activities_day_id", "trip_activities", ["day_id"])
    op.create_table("active_trip_selections",
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("trips.trip_id", ondelete="SET NULL"), unique=True),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("mutation_receipts",
        sa.Column("receipt_id", sa.Uuid(), primary_key=True), sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False), sa.Column("resource_scope", sa.String(128), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False), sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("result_resource_id", sa.String(128)), sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "operation", "resource_scope", "key_hash"))
    op.create_table("trip_lifecycle_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True), sa.Column("trip_id", sa.Uuid()), sa.Column("account_id", sa.Uuid()),
        sa.Column("event_type", sa.String(64), nullable=False), sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False), sa.Column("metadata_json", JSON_VALUE, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_trip_lifecycle_events_trip_id", "trip_lifecycle_events", ["trip_id"])
    op.create_index("ix_trip_lifecycle_events_account_id", "trip_lifecycle_events", ["account_id"])


def downgrade() -> None:
    for table in ("trip_lifecycle_events", "mutation_receipts", "active_trip_selections", "trip_activities", "trip_days", "trips", "traveler_profiles"):
        op.drop_table(table)
