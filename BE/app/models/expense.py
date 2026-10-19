from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from BE.app.models.base import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from BE.app.models.trip import Trip


class Expense(TimestampMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount_vnd >= 0", name="ck_expense_amount"),
        CheckConstraint("version >= 1", name="ck_expense_version"),
        CheckConstraint(
            "category IN ('food','ticket','transport','other')",
            name="ck_expense_category",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(24), default="other", nullable=False)
    spent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    notes: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    trip: Mapped["Trip"] = relationship(back_populates="expenses")
