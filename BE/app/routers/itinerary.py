"""POST /v1/itinerary (T020, lane C). TripRequest -> profile plans.

Retrieval/ranking are lane C; feasibility planning is owned by lane B. Until
that service is present, the endpoint fails explicitly instead of presenting
the former rank-order stub as a real itinerary.
"""

from __future__ import annotations

import importlib
import json
import os
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.config import get_settings
from BE.app.routers import error
from BE.app.routers import select as select_svc
from BE.app.schemas.trip import TripRequest
from BE.app.services import rank as rank_svc
from BE.app.services import retrieval as retrieval_svc

router = APIRouter(prefix="/v1", tags=["itinerary"])


class ItineraryIn(BaseModel):
    trip: TripRequest
    profiles: list[str] = ["balanced"]


def _get_plan_builder():
    """Return lane B's profile planner when available, otherwise fail closed."""
    module_name = "BE.app.services.profiles"
    try:
        profiles_svc = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return None
        raise
    builder = getattr(profiles_svc, "build_plan", None)
    return builder if callable(builder) else None


def _load_cells(snapshot_dir: str) -> dict:
    try:
        with open(os.path.join(snapshot_dir, "matrix.json"), encoding="utf-8") as f:
            return json.load(f).get("cells", {})
    except (FileNotFoundError, NotADirectoryError):
        return {}


@router.post("/itinerary")
def itinerary(body: ItineraryIn):
    settings = get_settings()
    try:
        pois = retrieval_svc.load_pois_json(
            os.path.join(settings.snapshot_dir, "pois.json"))
    except (FileNotFoundError, NotADirectoryError):
        return error("SNAPSHOT_MISSING",
                     f"snapshot dir {settings.snapshot_dir} chua co (doi lane A T003b)", 503)

    # The lane-B planner is intentionally optional on this branch. Do not
    # silently substitute a fake itinerary if its real feasibility seam is absent.
    builder = _get_plan_builder()
    if builder is None:
        return error("PLANNER_UNAVAILABLE",
                     "dich vu lap lich lane B chua kha dung tren branch nay", 501)

    trip = body.trip.model_dump()
    by_id = {p["poi_id"]: p for p in pois}
    retrieval = retrieval_svc.retrieve(trip, pois)
    candidate_ids = [c["poi_id"] for c in retrieval["candidates"]]
    ranked = rank_svc.rank(
        [by_id[poi_id] for poi_id in candidate_ids],
        {"budget": trip["budget"]},
        {"trip": trip, "hour": trip["start_time"]},
    )
    cells = _load_cells(settings.snapshot_dir)

    # TODO(lane B): align build_plan's adapter with the landed profiles API.
    plans = []
    for profile in body.profiles:
        plan = dict(builder(profile=profile, trip=trip, ranked=ranked,
                            pois_by_id=by_id, cells=cells))
        plan["itinerary_id"] = str(uuid4())
        plan["trip_id"] = body.trip.trip_id
        plan["profile"] = profile
        plans.append(plan)

    # Make every returned itinerary immediately selectable.
    select_svc.register(plans)
    return {"plans": plans, "selected": None}
