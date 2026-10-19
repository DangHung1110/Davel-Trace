"""Create route preview cache."""

from alembic import op
import sqlalchemy as sa

revision = "0004_route_segments"
down_revision = "0003_expenses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "route_segments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_activity_id", sa.String(36), nullable=False),
        sa.Column("to_activity_id", sa.String(36), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("is_real_route", sa.Boolean(), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_s", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("geometry", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_route_segments_trip_id", "route_segments", ["trip_id"])


def downgrade() -> None:
    op.drop_index("ix_route_segments_trip_id", table_name="route_segments")
    op.drop_table("route_segments")
