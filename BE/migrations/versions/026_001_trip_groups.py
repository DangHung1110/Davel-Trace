"""Private trip groups and shared travel records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "026_001"
down_revision = "013_001"
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "trip_group_plan_votes",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("voter_account_id", sa.Uuid(), nullable=False),
        sa.Column("alternative_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["alternative_id"],
            ["itinerary_alternatives.alternative_id"],
            name=op.f("fk_trip_group_plan_votes_alternative_id_itinerary_alternatives"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["planning_requests.request_id"],
            name=op.f("fk_trip_group_plan_votes_request_id_planning_requests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["voter_account_id"],
            ["accounts.account_id"],
            name=op.f("fk_trip_group_plan_votes_voter_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "request_id", "voter_account_id", name=op.f("pk_trip_group_plan_votes")
        ),
    )
    op.create_table(
        "trip_groups",
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trips.trip_id"],
            name=op.f("fk_trip_groups_trip_id_trips"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("trip_id", name=op.f("pk_trip_groups")),
    )
    op.create_table(
        "trip_group_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trip_groups.trip_id"],
            name=op.f("fk_trip_group_invites_trip_id_trip_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_group_invites")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_trip_group_invites_code_hash")),
    )
    op.create_index(
        op.f("ix_trip_group_invites_trip_id"),
        "trip_group_invites",
        ["trip_id"],
        unique=False,
    )
    op.create_table(
        "trip_group_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("is_guest", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.account_id"],
            name=op.f("fk_trip_group_members_account_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trip_groups.trip_id"],
            name=op.f("fk_trip_group_members_trip_id_trip_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_group_members")),
        sa.UniqueConstraint(
            "trip_id", "account_id", name=op.f("uq_trip_group_members_trip_id")
        ),
    )
    op.create_index(
        "ix_group_members_account_active",
        "trip_group_members",
        ["account_id", "active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trip_group_members_trip_id"),
        "trip_group_members",
        ["trip_id"],
        unique=False,
    )
    op.create_table(
        "trip_group_expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("payer_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column("split", JSON_VALUE, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('expense','settlement')",
            name=op.f("ck_trip_group_expenses_kind_valid"),
        ),
        sa.CheckConstraint(
            "amount_vnd > 0", name=op.f("ck_trip_group_expenses_amount_positive")
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_trip_group_expenses_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["trip_group_members.id"],
            name=op.f("fk_trip_group_expenses_author_id_trip_group_members"),
        ),
        sa.ForeignKeyConstraint(
            ["payer_id"],
            ["trip_group_members.id"],
            name=op.f("fk_trip_group_expenses_payer_id_trip_group_members"),
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trip_groups.trip_id"],
            name=op.f("fk_trip_group_expenses_trip_id_trip_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_group_expenses")),
    )
    op.create_index(
        "ix_group_expenses_ledger",
        "trip_group_expenses",
        ["trip_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "trip_group_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("text", sa.String(length=2000), nullable=False),
        sa.Column("poi_id", sa.String(length=128), nullable=True),
        sa.Column("place_name", sa.String(length=200), nullable=True),
        sa.Column("event_key", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('message','meeting','system')",
            name=op.f("ck_trip_group_messages_kind_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["trip_group_members.id"],
            name=op.f("fk_trip_group_messages_member_id_trip_group_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trip_groups.trip_id"],
            name=op.f("fk_trip_group_messages_trip_id_trip_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_group_messages")),
        sa.UniqueConstraint(
            "trip_id", "event_key", name=op.f("uq_trip_group_messages_trip_id")
        ),
    )
    op.create_index(
        "ix_group_messages_feed",
        "trip_group_messages",
        ["trip_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "trip_group_suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("poi_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=False),
        sa.Column("priority", sa.Boolean(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("preference_data", JSON_VALUE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('place','interest','food','avoid','accessibility','profile')",
            name=op.f("ck_trip_group_suggestions_kind_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["trip_group_members.id"],
            name=op.f("fk_trip_group_suggestions_member_id_trip_group_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trip_groups.trip_id"],
            name=op.f("fk_trip_group_suggestions_trip_id_trip_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_group_suggestions")),
    )
    op.create_index(
        op.f("ix_trip_group_suggestions_trip_id"),
        "trip_group_suggestions",
        ["trip_id"],
        unique=False,
    )
    op.create_table(
        "trip_group_expense_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("expense_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("before", JSON_VALUE, nullable=True),
        sa.Column("after", JSON_VALUE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["trip_group_expenses.id"],
            name=op.f("fk_trip_group_expense_changes_expense_id_trip_group_expenses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_group_expense_changes")),
    )
    op.create_index(
        op.f("ix_trip_group_expense_changes_expense_id"),
        "trip_group_expense_changes",
        ["expense_id"],
        unique=False,
    )
    op.create_table(
        "trip_group_suggestion_votes",
        sa.Column("suggestion_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["trip_group_members.id"],
            name=op.f("fk_trip_group_suggestion_votes_member_id_trip_group_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["trip_group_suggestions.id"],
            name=op.f(
                "fk_trip_group_suggestion_votes_suggestion_id_trip_group_suggestions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "suggestion_id", "member_id", name=op.f("pk_trip_group_suggestion_votes")
        ),
    )


def downgrade() -> None:
    op.drop_table("trip_group_suggestion_votes")
    op.drop_index(
        op.f("ix_trip_group_expense_changes_expense_id"),
        table_name="trip_group_expense_changes",
    )
    op.drop_table("trip_group_expense_changes")
    op.drop_index(
        op.f("ix_trip_group_suggestions_trip_id"), table_name="trip_group_suggestions"
    )
    op.drop_table("trip_group_suggestions")
    op.drop_index("ix_group_messages_feed", table_name="trip_group_messages")
    op.drop_table("trip_group_messages")
    op.drop_index("ix_group_expenses_ledger", table_name="trip_group_expenses")
    op.drop_table("trip_group_expenses")
    op.drop_index(
        op.f("ix_trip_group_members_trip_id"), table_name="trip_group_members"
    )
    op.drop_index("ix_group_members_account_active", table_name="trip_group_members")
    op.drop_table("trip_group_members")
    op.drop_index(
        op.f("ix_trip_group_invites_trip_id"), table_name="trip_group_invites"
    )
    op.drop_table("trip_group_invites")
    op.drop_table("trip_groups")
    op.drop_table("trip_group_plan_votes")
