"""SQLAlchemy query and serialization helpers for itinerary lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from BE.app.db.models import (
    AcceptanceRecordModel,
    ActiveItineraryVersionModel,
    ItineraryAlternativeModel,
    ItineraryVersionModel,
    ItineraryVersionTransitionModel,
    PlanningRequestModel,
    TripModel,
)
from BE.app.modules.identity.service import IdentityError


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def owned_trip(session, account_id: UUID, trip_id: UUID, *, lock: bool = False):
    query = select(TripModel).where(
        TripModel.trip_id == trip_id,
        TripModel.account_id == account_id,
        TripModel.lifecycle_state == "available",
    )
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if row is None:
        raise IdentityError("NOT_FOUND", "Không tìm thấy chuyến đi.", 404)
    return row


def owned_request(session, account_id: UUID, request_id: UUID):
    request_id = UUID(str(request_id))
    row = session.scalar(select(PlanningRequestModel).where(
        PlanningRequestModel.request_id == request_id,
        PlanningRequestModel.account_id == account_id,
    ))
    if row is None:
        raise IdentityError("NOT_FOUND", "Không tìm thấy yêu cầu lập lịch.", 404)
    return row


def owned_alternative(session, account_id: UUID, alternative_id: UUID, *, lock=False):
    alternative_id = UUID(str(alternative_id))
    query = select(ItineraryAlternativeModel).where(
        ItineraryAlternativeModel.alternative_id == alternative_id,
        ItineraryAlternativeModel.account_id == account_id,
    )
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if row is None:
        raise IdentityError("NOT_FOUND", "Không tìm thấy phương án.", 404)
    return row


def owned_version(session, account_id: UUID, version_id: UUID):
    version_id = UUID(str(version_id))
    row = session.scalar(select(ItineraryVersionModel).where(
        ItineraryVersionModel.version_id == version_id,
        ItineraryVersionModel.account_id == account_id,
    ))
    if row is None:
        raise IdentityError("NOT_FOUND", "Không tìm thấy phiên bản lịch trình.", 404)
    return row


def alternative_public(row: ItineraryAlternativeModel) -> dict:
    return {
        "alternative_id": str(row.alternative_id),
        "request_id": str(row.request_id),
        "profile": row.profile,
        "plan": row.plan_payload,
        "gate": row.gate_payload,
        "deterministic_rank": row.deterministic_rank,
        "deterministic_score": row.deterministic_score,
        "data_version": row.data_version,
        "selectability_state": row.selectability_state,
        "created_at": iso(row.created_at),
    }


def request_public(session, row: PlanningRequestModel) -> dict:
    alternatives = list(session.scalars(
        select(ItineraryAlternativeModel)
        .where(ItineraryAlternativeModel.request_id == row.request_id)
        .order_by(ItineraryAlternativeModel.deterministic_rank)
    ))
    return {
        "request_id": str(row.request_id),
        "trip_id": str(row.trip_id),
        "request_kind": row.request_kind,
        "status": row.status,
        "data_version": row.data_version,
        "target_count": row.target_count,
        "returned_count": row.returned_count,
        "shortage_reason": row.shortage_reason,
        "failure_code": row.failure_code,
        "source_version_id": str(row.source_version_id) if row.source_version_id else None,
        "remaining_context": row.remaining_context,
        "created_at": iso(row.created_at),
        "completed_at": iso(row.completed_at),
        "alternatives": [alternative_public(item) for item in alternatives],
    }


def version_summary(row: ItineraryVersionModel, active_id: UUID | None) -> dict:
    return {
        "version_id": str(row.version_id),
        "trip_id": str(row.trip_id),
        "ordinal": row.ordinal,
        "active": row.version_id == active_id,
        "parent_version_id": str(row.parent_version_id) if row.parent_version_id else None,
        "data_version": row.data_version,
        "deterministic_rank": row.deterministic_rank,
        "deterministic_score": row.deterministic_score,
        "gate": {
            "passed": bool(row.gate_payload.get("passed")),
            "families": row.gate_payload.get("families", {}),
        },
        "created_at": iso(row.created_at),
    }


def version_detail(row: ItineraryVersionModel, active_id: UUID | None) -> dict:
    return {
        **version_summary(row, active_id),
        "plan": row.plan_payload,
        "gate": row.gate_payload,
        "request": row.request_payload,
    }


def transition_public(row: ItineraryVersionTransitionModel) -> dict:
    return {
        "transition_id": str(row.transition_id),
        "trip_id": str(row.trip_id),
        "from_version_id": str(row.from_version_id) if row.from_version_id else None,
        "to_version_id": str(row.to_version_id),
        "reason": row.reason,
        "occurred_at": iso(row.occurred_at),
        "correlation_id": row.correlation_id,
    }


def acceptance_public(row: AcceptanceRecordModel) -> dict:
    return {
        "acceptance_id": str(row.acceptance_id),
        "version_id": str(row.itinerary_version_id),
        "alternative_id": str(row.alternative_id),
        "request_id": str(row.request_id),
        "selected_at": iso(row.selected_at),
        "data_version": row.data_version,
    }


def active_for_trip(session, trip_id: UUID, *, lock: bool = False):
    if lock:
        return session.scalar(select(ActiveItineraryVersionModel).where(
            ActiveItineraryVersionModel.trip_id == trip_id
        ).with_for_update())
    return session.get(ActiveItineraryVersionModel, trip_id)


def mark_trip_needs_review(session, trip: TripModel) -> None:
    """Preserve active evidence while flagging authoritative trip mutations."""
    if session.get(ActiveItineraryVersionModel, trip.trip_id) is not None:
        trip.review_state = "needs_review"
