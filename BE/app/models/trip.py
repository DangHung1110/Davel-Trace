from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from BE.app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from BE.app.models.expense import Expense
    from BE.app.models.profile import UserProfile
    from BE.app.models.route import RouteSegment


class Trip(TimestampMixin, Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("travelers >= 1", name="ck_trip_travelers"),
        CheckConstraint("budget_vnd >= 0", name="ck_trip_budget"),
        CheckConstraint("version >= 1", name="ck_trip_version"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(32), default="da-nang", nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_start: Mapped[time] = mapped_column(Time, nullable=False)
    day_end: Mapped[time] = mapped_column(Time, nullable=False)
    travelers: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    budget_vnd: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transport: Mapped[str] = mapped_column(
        String(32), default="motorbike", nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    profile: Mapped["UserProfile"] = relationship(back_populates="trips")
    itinerary: Mapped["Itinerary"] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", passive_deletes=True
    )
    route_segments: Mapped[list["RouteSegment"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", passive_deletes=True
    )


class Itinerary(TimestampMixin, Base):
    __tablename__ = "itineraries"
    __table_args__ = (CheckConstraint("version >= 1", name="ck_itinerary_version"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), unique=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="itinerary")
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="itinerary",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Activity.position",
    )


class Activity(TimestampMixin, Base):
    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint("itinerary_id", "position", name="uq_activity_position"),
        CheckConstraint("position >= 0", name="ck_activity_position"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_activity_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_activity_longitude"),
        CheckConstraint("estimated_cost_vnd >= 0", name="ck_activity_cost"),
        CheckConstraint("version >= 1", name="ck_activity_version"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    itinerary_id: Mapped[str] = mapped_column(
        ForeignKey("itineraries.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    poi_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    notes: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="visit", nullable=False)
    estimated_cost_vnd: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    itinerary: Mapped[Itinerary] = relationship(back_populates="activities")
