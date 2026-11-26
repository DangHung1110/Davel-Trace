"""Shared plan projection and explicit group planning policies."""

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import select

from BE.app.db.models import (
    ItineraryAlternativeModel,
    PlanningRequestModel,
    TripActivityModel,
    TripDayModel,
)
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.planning_lifecycle.infrastructure import active_for_trip


def _unique(*values):
    return list(dict.fromkeys(value for group in values for value in (group or ())))


def group_hard_inputs(inputs):
    return {
        field: sorted(set(inputs.get(field) or []))
        for field in ("must_visit", "avoid", "accessibility")
    }


def group_conditions_match(planning_request, inputs):
    recorded = planning_request.input_payload
    planned_headcount = (recorded.get("trip") or {}).get("traveler_count", 1)
    return int(
        inputs.get("attendee_count") or 0
    ) <= planned_headcount and group_hard_inputs(inputs) == recorded.get(
        "group_hard_inputs"
    )


def apply_group_inputs(snapshot, inputs):
    """Apply confirmed needs and aggregate interests without changing the user's profile."""
    snapshot["traveler_count"] = max(
        snapshot["traveler_count"],
        int(inputs.get("attendee_count") or 0),
    )
    for field in ("must_visit", "avoid", "food_preferences"):
        snapshot[field] = _unique(snapshot.get(field), inputs.get(field))
    if set(snapshot["must_visit"]) & set(snapshot["avoid"]):
        raise IdentityError(
            "GROUP_CONSTRAINT_CONFLICT",
            "Một địa điểm đang được đánh dấu vừa phải ghé vừa cần tránh. Hãy kiểm tra góp ý của nhóm.",
            422,
        )
    profile = dict(snapshot.get("profile_snapshot") or {})
    preferences = dict(snapshot.get("preference_overrides") or {})
    profile["accessibility_needs"] = _unique(
        profile.get("accessibility_needs"), inputs.get("accessibility")
    )
    for field in ("pace", "fitness"):
        supplied = inputs.get(field)
        if supplied is not None:
            saved = preferences.get(field, profile.get(field))
            preferences[field] = (
                min(saved, supplied) if saved in (1, 2, 3) else supplied
            )
    if inputs.get("outdoor_bias") is not None:
        preferences["outdoor_bias"] = inputs["outdoor_bias"]
    if snapshot["food_preferences"]:
        preferences["food_preferences"] = _unique(
            preferences.get("food_preferences", profile.get("food_preferences")),
            snapshot["food_preferences"],
        )
    if inputs.get("activities"):
        preferences["preferred_activities"] = _unique(
            preferences.get(
                "preferred_activities", profile.get("preferred_activities")
            ),
            inputs["activities"],
        )
    snapshot["profile_snapshot"] = profile
    snapshot["preference_overrides"] = preferences
    score = inputs.get("support_counts") or Counter(
        point
        for choices in inputs.get("priority_by_attendee", [])
        for point in set(choices)
    )
    # Preserve contribution order as the tiebreaker when the capped pool is full.
    points = _unique(inputs.get("priority_poi_ids"), sorted(score))
    points.sort(key=lambda point: -score.get(point, 0))
    snapshot["soft_poi_weights"] = {
        point: min(100, score.get(point) or 1) for point in points[:40]
    }


def ranked_group_plans(plans, group_inputs):
    """Prefer plans that cover different travellers before counting more of their picks."""
    priorities = [
        set(points) for points in group_inputs.get("priority_by_attendee", [])
    ]
    if not priorities:
        return plans

    def coverage(plan):
        places = {activity.get("poi_id") for activity in plan.get("activities") or []}
        hits = [len(choices & places) for choices in priorities]
        return sum(hit > 0 for hit in hits), sum(hits)

    return sorted(plans, key=coverage, reverse=True)


def latest_group_round(session, trip, data_version):
    """The most recent viable round. Once it is closed, older rounds stay closed."""
    active = active_for_trip(session, trip.trip_id)
    query = select(PlanningRequestModel).where(
        PlanningRequestModel.trip_id == trip.trip_id,
        PlanningRequestModel.trip_version == trip.version,
        PlanningRequestModel.data_version == data_version,
        PlanningRequestModel.status == "completed",
        PlanningRequestModel.returned_count > 0,
        PlanningRequestModel.input_payload["group_collaboration"]
        .as_boolean()
        .is_(True),
    )
    if active is not None:
        query = query.where(PlanningRequestModel.created_at > active.updated_at)
    return session.scalar(
        query.order_by(
            PlanningRequestModel.created_at.desc(),
            PlanningRequestModel.request_id.desc(),
        ).limit(1)
    )


def available_alternatives(session, planning_request):
    if planning_request is None:
        return []
    return list(
        session.scalars(
            select(ItineraryAlternativeModel)
            .where(
                ItineraryAlternativeModel.request_id == planning_request.request_id,
                ItineraryAlternativeModel.selectability_state == "current",
            )
            .order_by(ItineraryAlternativeModel.deterministic_rank)
        )
    )


def saved_plan_stops(plan, start_date, version_id):
    """Stable IDs for accepted planner stops that are not stored as manual activities."""
    window = plan.get("window") or {}
    day_offset = max(0, int(window.get("day") or 1) - 1)
    first_date = date.fromisoformat(plan["group_plan_date"]) if plan.get(
        "group_plan_date"
    ) else start_date + timedelta(days=day_offset)
    for index, item in enumerate(plan.get("activities") or []):
        day_in_window = max(1, int(item.get("day") or 1))
        yield {
            "id": f"plan:{version_id}:{index}",
            "poi_id": item.get("poi_id"),
            "name": item.get("name") or item.get("title"),
            "start": item.get("start") or item.get("start_time"),
            "end": item.get("end") or item.get("end_time"),
            "day": day_in_window + day_offset,
            "date": (first_date + timedelta(days=day_in_window - 1)).isoformat(),
            "status": "planned",
        }


def stop_order(stop):
    return (stop["date"], stop.get("start") or "", stop.get("position", 0), stop["id"])


def trip_stops(session, trip, version):
    """Live manual activities, retained progress and the currently planned stops."""
    rows = session.execute(
        select(TripActivityModel, TripDayModel.local_date)
        .join(TripDayModel, TripActivityModel.day_id == TripDayModel.day_id)
        .where(TripDayModel.trip_id == trip.trip_id)
    )
    manual = [
        {
            "id": str(activity.activity_id),
            "poi_id": activity.poi_id,
            "name": activity.title,
            "start": activity.start_time.isoformat()[:5]
            if activity.start_time
            else None,
            "end": activity.end_time.isoformat()[:5] if activity.end_time else None,
            "day": (local_date - trip.start_date).days + 1,
            "date": local_date.isoformat(),
            "status": activity.progress_state,
            "position": activity.position,
        }
        for activity, local_date in rows
    ]
    if version is None:
        return sorted(manual, key=stop_order)
    retained = version.plan_payload.get("group_retained_stops") or []
    occupied = {(stop["date"], stop["poi_id"], stop.get("start")) for stop in manual}
    populated = {stop["id"]: stop for stop in manual}
    for stop in retained:
        manual_stop = populated.get(stop["id"])
        if manual_stop is None or manual_stop["status"] == "planned":
            populated[stop["id"]] = stop
    for stop in saved_plan_stops(
        version.plan_payload, trip.start_date, version.version_id
    ):
        if (stop["date"], stop["poi_id"], stop.get("start")) not in occupied:
            populated[stop["id"]] = stop
    return sorted(populated.values(), key=stop_order)
