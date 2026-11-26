"""Group-safe shared schedule, proposal voting and route preview."""

from collections import Counter
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from BE.app.core.config import get_settings
from BE.app.db.models import ItineraryVersionModel
from BE.app.db.session import session_scope
from BE.app.modules.catalog.domain import CatalogUnavailable
from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.planning_lifecycle.group_plans import (
    available_alternatives,
    group_conditions_match,
    latest_group_round,
    saved_plan_stops,
    trip_stops,
)
from BE.app.modules.planning_lifecycle.infrastructure import active_for_trip, iso
from BE.app.modules.routing.application import route_for_places
from BE.app.modules.trip_groups.models import GroupPlanVoteModel
from BE.app.modules.trip_groups.service import group_planning_inputs, require_trip_group
from sqlalchemy import select

router = APIRouter(prefix="/v1/trip-groups", tags=["trip-group-planning"])


class VoteBody(BaseModel):
    alternative_id: UUID | None


class RouteBody(BaseModel):
    plan_id: UUID
    day: int | None = Field(default=None, ge=1, le=30)


def _catalog(request):
    try:
        return request.app.state.catalog_reader()
    except (OSError, CatalogUnavailable):
        return None


def _stops_public(stops, catalog):
    places = {point["poi_id"]: point for point in (catalog or {}).get("pois", ())}
    result = []
    for stop in stops:
        point = places.get(stop.get("poi_id")) or {}
        result.append(
            {
                "id": stop["id"],
                "poi_id": stop.get("poi_id"),
                "name": stop.get("name") or point.get("name") or "Điểm dừng",
                "start": stop.get("start"),
                "end": stop.get("end"),
                "day": stop["day"],
                "date": stop["date"],
                "status": stop["status"],
                "lat": point.get("lat"),
                "lon": point.get("lon"),
            }
        )
    return result


def _overview(plan):
    return {
        "total_km": plan.get("total_km") or 0,
        "total_cost_vnd": plan.get("total_cost") or 0,
        "priority_matches": plan.get("group_priority_matches") or [],
        "priority_unmatched": plan.get("group_priority_unmatched") or [],
    }


def _round_for_review(session, trip, snapshot_name):
    latest = latest_group_round(session, trip, snapshot_name)
    # A new approved requirement makes previously computed drafts unsafe to vote on.
    if latest is not None and not group_conditions_match(
        latest, group_planning_inputs(session, trip.trip_id)
    ):
        return None, []
    return latest, available_alternatives(session, latest)


def shared_plan_snapshot(session, trip, account_id, snapshot_name, catalog):
    active = active_for_trip(session, trip.trip_id)
    version = session.get(ItineraryVersionModel, active.version_id) if active else None
    active_public = None
    if version is not None:
        active_public = {
            "id": str(version.version_id),
            "ordinal": version.ordinal,
            "updated_at": iso(active.updated_at),
            "activities": _stops_public(trip_stops(session, trip, version), catalog),
            **_overview(version.plan_payload),
        }
    current, alternatives = _round_for_review(session, trip, snapshot_name)
    round_public = None
    if current is not None and alternatives:
        votes = list(
            session.scalars(
                select(GroupPlanVoteModel).where(
                    GroupPlanVoteModel.request_id == current.request_id
                )
            )
        )
        counts = Counter(vote.alternative_id for vote in votes)
        selected = next(
            (
                vote.alternative_id
                for vote in votes
                if vote.voter_account_id == account_id
            ),
            None,
        )
        round_public = {
            "id": str(current.request_id),
            "status": current.status,
            "kind": current.request_kind,
            "my_vote": str(selected) if selected else None,
            "alternatives": [
                {
                    "id": str(item.alternative_id),
                    "rank": item.deterministic_rank,
                    "profile": item.profile,
                    "activities": _stops_public(
                        saved_plan_stops(
                            item.plan_payload, trip.start_date, item.alternative_id
                        ),
                        catalog,
                    ),
                    "vote_count": counts[item.alternative_id],
                    **_overview(item.plan_payload),
                }
                for item in alternatives
            ],
        }
    return {"active": active_public, "round": round_public}


@router.get("/{trip_id}/plans")
def group_plans(
    trip_id: UUID, request: Request, current: Principal = Depends(current_principal)
):
    settings = get_settings()
    with session_scope(settings.database_url) as session:
        trip = require_trip_group(session, current.account_id, trip_id)
        return shared_plan_snapshot(
            session, trip, current.account_id, settings.snapshot_name, _catalog(request)
        )


@router.put("/{trip_id}/plans/{request_id}/vote")
def vote(
    trip_id: UUID,
    request_id: UUID,
    body: VoteBody,
    request: Request,
    current: Principal = Depends(current_principal),
):
    settings = get_settings()
    with session_scope(settings.database_url) as session:
        trip = require_trip_group(session, current.account_id, trip_id, lock=True)
        latest, alternatives = _round_for_review(session, trip, settings.snapshot_name)
        if (
            trip.lifecycle_state != "available"
            or latest is None
            or latest.request_id != request_id
            or not alternatives
        ):
            raise IdentityError(
                "ROUND_CLOSED", "Vòng bình chọn đã kết thúc. Hãy xem lịch mới.", 409
            )
        if body.alternative_id is not None and not any(
            item.alternative_id == body.alternative_id for item in alternatives
        ):
            raise IdentityError(
                "NOT_FOUND", "Không tìm thấy phương án trong chuyến đi.", 404
            )
        existing = session.get(GroupPlanVoteModel, (request_id, current.account_id))
        if body.alternative_id is None:
            if existing is not None:
                session.delete(existing)
        elif existing is None:
            session.add(
                GroupPlanVoteModel(
                    request_id=request_id,
                    voter_account_id=current.account_id,
                    alternative_id=body.alternative_id,
                )
            )
        else:
            existing.alternative_id = body.alternative_id
        session.flush()
        return shared_plan_snapshot(
            session, trip, current.account_id, settings.snapshot_name, _catalog(request)
        )


@router.post("/{trip_id}/plans/route")
def group_plan_route(
    trip_id: UUID,
    body: RouteBody,
    request: Request,
    current: Principal = Depends(current_principal),
):
    settings = get_settings()
    with session_scope(settings.database_url) as session:
        trip = require_trip_group(session, current.account_id, trip_id)
        active = active_for_trip(session, trip_id)
        if active is not None and active.version_id == body.plan_id:
            version = session.get(ItineraryVersionModel, body.plan_id)
            stops = trip_stops(session, trip, version)
        else:
            _, alternatives = _round_for_review(session, trip, settings.snapshot_name)
            item = next(
                (item for item in alternatives if item.alternative_id == body.plan_id),
                None,
            )
            if item is None:
                raise IdentityError(
                    "NOT_FOUND", "Không tìm thấy lịch của chuyến đi.", 404
                )
            stops = list(
                saved_plan_stops(
                    item.plan_payload, trip.start_date, item.alternative_id
                )
            )
        day = (
            body.day
            if body.day is not None
            else next(
                (stop["day"] for stop in stops if stop["status"] != "skipped"), None
            )
        )
        ids = [
            stop["poi_id"]
            for stop in stops
            if stop["day"] == day and stop["status"] != "skipped" and stop["poi_id"]
        ][:25]
    catalog = _catalog(request)
    if catalog is None:
        raise IdentityError(
            "CATALOG_UNAVAILABLE", "Chưa tải được địa điểm trên bản đồ.", 503
        )
    try:
        matrix = request.app.state.matrix_reader()
    except (OSError, CatalogUnavailable):
        matrix = {}
    return route_for_places(
        ids,
        catalog,
        matrix,
        request.app.state.route_provider,
        request.app.state.matrix_estimator,
    )
