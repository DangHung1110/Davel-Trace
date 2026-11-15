"""Persistent Google subjects and browser-bound, expiring sign-in transactions."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from BE.app.db.base import Base
from BE.app.db.models import utc_now


class GoogleIdentityModel(Base):
    __tablename__ = "google_identities"

    subject: Mapped[str] = mapped_column(String(255), primary_key=True)
    account_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("accounts.account_id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GoogleLoginAttemptModel(Base):
    __tablename__ = "google_login_attempts"

    attempt_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    browser_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    application_origin: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    callback_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handoff_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    handoff_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exchanged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    account_id: Mapped[UUID | None] = mapped_column(
        Uuid(), ForeignKey("accounts.account_id", ondelete="CASCADE"),
    )
