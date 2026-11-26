"""Allow replies and a pinned meeting point in each group."""
import sqlalchemy as sa
from alembic import op

revision = "026_002"
down_revision = "026_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trip_groups", sa.Column("pinned_message_id", sa.Uuid(), nullable=True))
    op.add_column("trip_group_messages", sa.Column("reply_to_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("trip_group_messages", "reply_to_id")
    op.drop_column("trip_groups", "pinned_message_id")
