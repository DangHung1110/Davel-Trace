"""Persistence for group participants and their contributions."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from BE.app.db.base import Base
from BE.app.db.models import JSON_VALUE, utc_now


class TripGroupModel(Base):
    __tablename__ = "trip_groups"

    trip_id: Mapped[UUID] = mapped_column(
        ForeignKey("trips.trip_id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    pinned_message_id: Mapped[UUID | None] = mapped_column(Uuid())


class GroupMemberModel(Base):
    __tablename__ = "trip_group_members"
    __table_args__ = (
        UniqueConstraint("trip_id", "account_id"),
        Index("ix_group_members_account_active", "account_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    trip_id: Mapped[UUID] = mapped_column(
        ForeignKey("trip_groups.trip_id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.account_id", ondelete="SET NULL")
    )
    display_name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class GroupInviteModel(Base):
    __tablename__ = "trip_group_invites"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    trip_id: Mapped[UUID] = mapped_column(
        ForeignKey("trip_groups.trip_id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class GroupSuggestionModel(Base):
    __tablename__ = "trip_group_suggestions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('place','interest','food','avoid','accessibility','profile')",
            name="kind_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    trip_id: Mapped[UUID] = mapped_column(
        ForeignKey("trip_groups.trip_id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[UUID] = mapped_column(
        ForeignKey("trip_group_members.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(20))
    poi_id: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(String(500), default="")
    priority: Mapped[bool] = mapped_column(Boolean, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    preference_data: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class GroupSuggestionVoteModel(Base):
    __tablename__ = "trip_group_suggestion_votes"

    suggestion_id: Mapped[UUID] = mapped_column(
        ForeignKey("trip_group_suggestions.id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[UUID] = mapped_column(
        ForeignKey("trip_group_members.id", ondelete="CASCADE"), primary_key=True
    )


class GroupMessageModel(Base):
    __tablename__ = "trip_group_messages"
    __table_args__ = (
        UniqueConstraint("trip_id", "event_key"),
        CheckConstraint("kind IN ('message','meeting','system')", name="kind_valid"),
        Index("ix_group_messages_feed", "trip_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    trip_id: Mapped[UUID] = mapped_column(
        ForeignKey("trip_groups.trip_id", ondelete="CASCADE")
    )
    member_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("trip_group_members.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(String(2000))
    poi_id: Mapped[str | None] = mapped_column(String(128))
    place_name: Mapped[str | None] = mapped_column(String(200))
    reply_to_id: Mapped[UUID | None] = mapped_column(Uuid())
    event_key: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class GroupExpenseModel(Base):
    __tablename__ = "trip_group_expenses"
    __table_args__ = (
        CheckConstraint("kind IN ('expense','settlement','contribution')", name="kind_valid"),
        CheckConstraint(
            "(kind = 'contribution' AND source = 'fund' AND method IS NOT NULL "
            "AND method IN ('manual','demo')) OR "
            "(kind = 'expense' AND source IN ('personal','fund') AND method IS NULL) OR "
            "(kind = 'settlement' AND source = 'personal' AND method IS NULL)",
            name="fund_fields_valid",
        ),
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        Index("ix_group_expenses_ledger", "trip_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    trip_id: Mapped[UUID] = mapped_column(
        ForeignKey("trip_groups.trip_id", ondelete="CASCADE")
    )
    author_id: Mapped[UUID] = mapped_column(ForeignKey("trip_group_members.id"))
    payer_id: Mapped[UUID] = mapped_column(ForeignKey("trip_group_members.id"))
    kind: Mapped[str] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(12), server_default="personal")
    note: Mapped[str] = mapped_column(String(500), server_default="")
    method: Mapped[str | None] = mapped_column(String(12))
    amount_vnd: Mapped[int] = mapped_column(BigInteger)
    split: Mapped[dict] = mapped_column(JSON_VALUE)
    version: Mapped[int] = mapped_column(default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class GroupExpenseChangeModel(Base):
    __tablename__ = "trip_group_expense_changes"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    expense_id: Mapped[UUID] = mapped_column(
        ForeignKey("trip_group_expenses.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[UUID] = mapped_column(Uuid())
    action: Mapped[str] = mapped_column(String(20))
    before: Mapped[dict | None] = mapped_column(JSON_VALUE)
    after: Mapped[dict | None] = mapped_column(JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class GroupPlanVoteModel(Base):
    __tablename__ = "trip_group_plan_votes"

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_requests.request_id", ondelete="CASCADE"), primary_key=True
    )
    voter_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.account_id", ondelete="CASCADE"), primary_key=True
    )
    alternative_id: Mapped[UUID] = mapped_column(
        ForeignKey("itinerary_alternatives.alternative_id", ondelete="CASCADE")
    )
