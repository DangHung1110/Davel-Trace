"""Support contributions and spending from the group fund."""

import sqlalchemy as sa
from alembic import op

revision = "026_003"
down_revision = "026_002"
branch_labels = None
depends_on = None

TABLE = "trip_group_expenses"
KIND_CONSTRAINT = "ck_trip_group_expenses_kind_valid"
FUND_CONSTRAINT = "ck_trip_group_expenses_fund_fields_valid"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(sa.Column("source", sa.String(12), nullable=False, server_default="personal"))
        batch.add_column(sa.Column("note", sa.String(500), nullable=False, server_default=""))
        batch.add_column(sa.Column("method", sa.String(12), nullable=True))
        batch.drop_constraint(op.f(KIND_CONSTRAINT), type_="check")
        batch.create_check_constraint(
            op.f(KIND_CONSTRAINT), "kind IN ('expense','settlement','contribution')"
        )
        batch.create_check_constraint(
            op.f(FUND_CONSTRAINT),
            "(kind = 'contribution' AND source = 'fund' AND method IS NOT NULL "
            "AND method IN ('manual','demo')) OR "
            "(kind = 'expense' AND source IN ('personal','fund') AND method IS NULL) OR "
            "(kind = 'settlement' AND source = 'personal' AND method IS NULL)",
        )


def downgrade() -> None:
    # Preserve fund records, including soft-deleted and audited contributions.
    has_fund_records = op.get_bind().scalar(
        sa.text("SELECT 1 FROM trip_group_expenses WHERE source = 'fund' LIMIT 1")
    )
    if has_fund_records:
        raise RuntimeError("Cannot downgrade a database with recorded group fund activity.")
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint(op.f(FUND_CONSTRAINT), type_="check")
        batch.drop_constraint(op.f(KIND_CONSTRAINT), type_="check")
        batch.create_check_constraint(
            op.f(KIND_CONSTRAINT), "kind IN ('expense','settlement')"
        )
        batch.drop_column("method")
        batch.drop_column("note")
        batch.drop_column("source")
