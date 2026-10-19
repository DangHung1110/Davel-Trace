"""Create trips, itineraries and manual activities."""

from alembic import op
import sqlalchemy as sa

revision = "0002_trip_itinerary"
down_revision = "0001_management_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("city", sa.String(32), nullable=False, server_default="da-nang"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("day_start", sa.Time(), nullable=False),
        sa.Column("day_end", sa.Time(), nullable=False),
        sa.Column("travelers", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("budget_vnd", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transport", sa.String(32), nullable=False, server_default="motorbike"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("travelers >= 1", name="ck_trip_travelers"),
        sa.CheckConstraint("budget_vnd >= 0", name="ck_trip_budget"),
        sa.CheckConstraint("version >= 1", name="ck_trip_version"),
    )
    op.create_index("ix_trips_profile_id", "trips", ["profile_id"])
    op.create_table(
        "itineraries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_itinerary_version"),
    )
    op.create_index("ix_itineraries_trip_id", "itineraries", ["trip_id"], unique=True)
    op.create_table(
        "activities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("itinerary_id", sa.String(36), sa.ForeignKey("itineraries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("poi_id", sa.String(120), nullable=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=False, server_default=""),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(40), nullable=False, server_default="visit"),
        sa.Column("estimated_cost_vnd", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("itinerary_id", "position", name="uq_activity_position"),
        sa.CheckConstraint("position >= 0", name="ck_activity_position"),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_activity_latitude"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_activity_longitude"),
        sa.CheckConstraint("estimated_cost_vnd >= 0", name="ck_activity_cost"),
        sa.CheckConstraint("version >= 1", name="ck_activity_version"),
    )
    op.create_index("ix_activities_itinerary_id", "activities", ["itinerary_id"])
    op.create_index("ix_activities_poi_id", "activities", ["poi_id"])


def downgrade() -> None:
    op.drop_index("ix_activities_poi_id", table_name="activities")
    op.drop_index("ix_activities_itinerary_id", table_name="activities")
    op.drop_table("activities")
    op.drop_index("ix_itineraries_trip_id", table_name="itineraries")
    op.drop_table("itineraries")
    op.drop_index("ix_trips_profile_id", table_name="trips")
    op.drop_table("trips")
