from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from BE.app.models.base import Base, utc_now

if TYPE_CHECKING:
    from BE.app.models.trip import Trip


class RouteSegment(Base):
    __tablename__ = "route_segments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    trip_id: Mapped[str] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), index=True
    )
    from_activity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    to_activity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    is_real_route: Mapped[bool] = mapped_column(Boolean, nullable=False)
    distance_m: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    geometry: Mapped[list[list[float]]] = mapped_column(JSON, default=list, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    trip: Mapped["Trip"] = relationship(back_populates="route_segments")
