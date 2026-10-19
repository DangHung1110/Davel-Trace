"""Create profile and device state tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_management_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("language", sa.String(8), nullable=False, server_default="vi"),
        sa.Column("party_type", sa.String(24), nullable=False, server_default="solo"),
        sa.Column("trip_purpose", sa.String(24), nullable=False, server_default="leisure"),
        sa.Column("spending_level", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("pace", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("fitness", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("food_preferences", sa.JSON(), nullable=False),
        sa.Column("must_avoid", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("spending_level BETWEEN 1 AND 3", name="ck_profile_spending"),
        sa.CheckConstraint("pace BETWEEN 1 AND 3", name="ck_profile_pace"),
        sa.CheckConstraint("fitness BETWEEN 1 AND 3", name="ck_profile_fitness"),
    )
    op.create_table(
        "device_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "active_profile_id",
            sa.String(36),
            sa.ForeignKey("user_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("device_state")
    op.drop_table("user_profiles")
