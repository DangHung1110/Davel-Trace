"""Create trip expenses."""

from alembic import op
import sqlalchemy as sa

revision = "0003_expenses"
down_revision = "0002_trip_itinerary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(24), nullable=False, server_default="other"),
        sa.Column("spent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_vnd >= 0", name="ck_expense_amount"),
        sa.CheckConstraint("version >= 1", name="ck_expense_version"),
        sa.CheckConstraint("category IN ('food','ticket','transport','other')", name="ck_expense_category"),
    )
    op.create_index("ix_expenses_trip_id", "expenses", ["trip_id"])
    op.create_index("ix_expenses_spent_at", "expenses", ["spent_at"])
    op.create_index("ix_expenses_trip_category_time", "expenses", ["trip_id", "category", "spent_at"])


def downgrade() -> None:
    op.drop_index("ix_expenses_trip_category_time", table_name="expenses")
    op.drop_index("ix_expenses_spent_at", table_name="expenses")
    op.drop_index("ix_expenses_trip_id", table_name="expenses")
    op.drop_table("expenses")
