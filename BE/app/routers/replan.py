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
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.routers import error
from BE.app.routers import select as select_svc
from BE.app.services import state as store
from BE.app.services.replan import replan as replan_service

router = APIRouter(prefix="/v1", tags=["replan"])


class ReplanIn(BaseModel):
    itinerary_id: str
    event: dict = {}
    completed: list[str | dict] = []
    budget_state: dict | None = None


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
    st = store.new_state(trip_id, acts, trip.get("start_time", "07:00"))
    for item in body.completed:
        pid = item if isinstance(item, str) else item.get("poi_id")
        at = "" if isinstance(item, str) else item.get("at", "")
        if pid:
            st = store.complete(st, pid, at)

    return replan_service(st, body.event, pois, travel, trip,
                          budget_state=body.budget_state)
