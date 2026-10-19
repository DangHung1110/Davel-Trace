from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from BE.app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from BE.app.models.trip import Trip


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint("spending_level BETWEEN 1 AND 3", name="ck_profile_spending"),
        CheckConstraint("pace BETWEEN 1 AND 3", name="ck_profile_pace"),
        CheckConstraint("fitness BETWEEN 1 AND 3", name="ck_profile_fitness"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="vi", nullable=False)
    party_type: Mapped[str] = mapped_column(String(24), default="solo", nullable=False)
    trip_purpose: Mapped[str] = mapped_column(
        String(24), default="leisure", nullable=False
    )
    spending_level: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    pace: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    fitness: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    food_preferences: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    must_avoid: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    trips: Mapped[list["Trip"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )


class DeviceState(TimestampMixin, Base):
    __tablename__ = "device_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    active_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="SET NULL"), nullable=True
    )
    active_profile: Mapped[UserProfile | None] = relationship()
