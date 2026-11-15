"""Google identity and ephemeral sign-in state; additive to existing accounts."""

from alembic import op
import sqlalchemy as sa

revision = "013_001"
down_revision = "010_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "google_identities",
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "google_login_attempts",
        sa.Column("attempt_id", sa.Uuid(), primary_key=True),
        sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("application_origin", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("callback_used_at", sa.DateTime(timezone=True)),
        sa.Column("handoff_hash", sa.String(64), unique=True),
        sa.Column("handoff_expires_at", sa.DateTime(timezone=True)),
        sa.Column("exchanged_at", sa.DateTime(timezone=True)),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.account_id", ondelete="CASCADE")),
    )
    op.create_index("ix_google_login_attempts_expires_at", "google_login_attempts", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_google_login_attempts_expires_at", table_name="google_login_attempts")
    op.drop_table("google_login_attempts")
    op.drop_table("google_identities")
