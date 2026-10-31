"""POST /v1/replan (T020 shell + T046 logic, wired at T061e).

In (contracts/api.md): {"itinerary_id": "...", "event": {DynamicEvent}}.
Out: {"itinerary": {Itinerary v+1}, "mode": "plan|clarify|no_solution",
"changes": [...]}. Rule: completed activities preserved; version++.

The lane-B rolling-horizon service (`BE.app.services.replan.replan`) owns
the logic; this shell rebuilds the trip state from the stored plan and
exposes it. Two optional fields keep the demo usable without inventing a
new contract: `completed` (mark done items before replanning, so the
rolling horizon advances) and `budget_state` (lane-C `replan_budget()`
snapshot -> actual remaining, T036b). Unknown itinerary -> 404 envelope.

A plan of several days replans one day (`day`, default: the first with stops
still to do). The other days come back unchanged in the new itinerary.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.routers import error
from BE.app.routers import select as select_svc
from BE.app.services import multiday
from BE.app.services import state as store
from BE.app.services.replan import replan as replan_service

router = APIRouter(prefix="/v1", tags=["replan"])


class ReplanIn(BaseModel):
    itinerary_id: str
    event: dict = {}
    completed: list[str | dict] = []
    budget_state: dict | None = None
    day: int | None = None


def _travel(matrix: dict) -> dict:
    """{"a->b": {"minutes": n}} -> {(a, b): n} (missing stays absent, B3)."""
    out = {}
    for key, cell in (matrix or {}).items():
        if "->" not in key or not isinstance(cell, dict):
            continue
        a, b = key.split("->", 1)
        if a != b:
            out[(a, b)] = int(cell["minutes"])
    return out


@router.post("/replan")
def replan_endpoint(body: ReplanIn):
    plan = select_svc.get_store()["plans"].get(body.itinerary_id)
    if plan is None:
        return error("UNKNOWN_ITINERARY",
                     f"khong co plan {body.itinerary_id}", 404)

    ctx = plan.get("_context") or {}
    trip = ctx.get("trip") or plan.get("trip") or {}
    pois = ctx.get("pois") or []
    travel = ctx.get("travel") or _travel(plan.get("matrix") or {})
    if not trip or not pois:
        return error("REPLAN_CONTEXT_MISSING",
                     "plan thieu ngu canh de replan (trip/pois)", 409)

    trip_id = plan.get("trip_id", trip.get("trip_id", "t1"))
    acts = plan.get("activities", [])
    day, others = None, []
    if plan.get("days"):
        done = {item if isinstance(item, str) else item.get("poi_id") for item in body.completed}
        day = body.day if body.day is not None else multiday.active_day(acts, done)
        today = [a for a in acts if a.get("day") == day]
        if not today:
            return error("UNKNOWN_DAY", f"lich khong co ngay {day}", 404)
        others = [a for a in acts if a.get("day") != day]
        acts = [{k: v for k, v in a.items() if k != "day"} for a in today]
        trip = multiday.day_scope(trip, others, today, {p["poi_id"]: p for p in pois})
    other_ids = {a["poi_id"] for a in others}
    pois = [p for p in pois if p["poi_id"] not in other_ids]  # a substitute must be new
    st = store.new_state(trip_id, acts, trip.get("start_time", "07:00"))
    for item in body.completed:
        pid = item if isinstance(item, str) else item.get("poi_id")
        at = "" if isinstance(item, str) else item.get("at", "")
        if pid in other_ids:
            continue  # done on another day: that day stays as it is
        if pid:
            # T053 fix: an unknown/duplicate completed poi_id used to reach
            # state.complete(), whose KeyError escaped as a 500. Answer with
            # the contracts/api.md error envelope instead.
            remaining = {a["poi_id"] for a in st["remaining"]}
            if pid not in remaining:
                return error("UNKNOWN_POI",
                             f"poi {pid} khong co trong itinerary", 404)
            st = store.complete(st, pid, at)

    out = replan_service(st, body.event, pois, travel, trip,
                         budget_state=body.budget_state)
    if day is None:
        return out
    out["day"] = day
    if out.get("itinerary"):
        new_today = [{**a, "day": day} for a in out["itinerary"]["activities"]]
        out["itinerary"]["activities"] = sorted(
            others + new_today, key=lambda a: (a["day"], a["start"]))
    return out
