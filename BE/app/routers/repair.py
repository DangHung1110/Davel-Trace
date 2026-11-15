"""POST /v1/repair (NOTE(test-local), do NOT PR as-is).

LLM-guided semantic repair with a bounded loop (max 2 rounds):

In:  {"itinerary_id": "..."}  (read from the select store) or
     {"plan": {...}, "trip": {...}}.
Out: {"plan": {...}, "rounds": n,
      "repairs": [{"issue", "action", "kept"}, ...],
      "gate": {...}, "review_ms": [...]}

Per round: narrow LLM review (the exact /v1/review prompt) -> safe POI swaps
(different category, same time slot, verified + matrix-connected) -> gate
re-validation. A swap is kept only when every HARD gate still passes. The
loop stops after 2 rounds, zero high/medium issues, or a round that kept no
repair. Any LLM failure returns the current plan with a note (never 500).

Times/costs are never edited by hand: the swap keeps the activity's
start/end and `repair._refresh` recomputes totals/segments/status from the
shared helpers. `soft_violations` (F1) may remain when the verified +
matrix-covered pool has no non-food alternative — that is reported, not
faked.
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.config import get_settings
from BE.app.routers import error
from BE.app.routers import evaluate as evaluate_router
from BE.app.routers import review as review_router
from BE.app.routers import select as select_svc
from BE.app.services import repair as repair_svc
from BE.app.services import retrieval as retrieval_svc

router = APIRouter(prefix="/v1", tags=["repair"])


class RepairIn(BaseModel):
    itinerary_id: str | None = None
    plan: dict | None = None
    trip: dict | None = None


def _matrix_from_travel(travel: dict) -> dict:
    """{(a, b): minutes} (plan context) -> {"a->b": {"minutes": n}}."""
    return {f"{a}->{b}": {"minutes": int(minutes)}
            for (a, b), minutes in travel.items()}


def _as_index(raw) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    return {p["poi_id"]: p for p in raw or [] if p.get("poi_id")}


def _resolve(body: RepairIn):
    """(plan, trip, pois_by_id, pool, matrix) or an error response."""
    plan = body.plan
    if plan is None:
        if not body.itinerary_id:
            return None, error("VALIDATION_ERROR",
                               "can itinerary_id hoac plan+trip", 422)
        plan = select_svc.get_store()["plans"].get(body.itinerary_id)
        if plan is None:
            return None, error("UNKNOWN_ITINERARY",
                               f"khong co plan {body.itinerary_id}", 404)

    ctx = plan.get("_context") or {}
    trip = body.trip or ctx.get("trip") or plan.get("trip")
    if not trip:
        return None, error("VALIDATION_ERROR",
                           "can trip (plan khong co _context.trip)", 422)

    snapshot_dir = get_settings().snapshot_dir
    loaded = evaluate_router.load_eval_context(snapshot_dir)
    if loaded is None:
        return None, error("SNAPSHOT_MISSING",
                           f"snapshot dir {snapshot_dir} chua co", 503)
    pois_by_id, cells = loaded

    raw_pool = ctx.get("pois") or plan.get("pois")
    if raw_pool:
        pool = list(pois_by_id.get(p.get("poi_id"), p) for p in _as_index(raw_pool).values())
    else:
        # No stored candidate pool: reproduce the router's retrieval seam so
        # the repair can only choose POIs the planner could have chosen.
        try:
            all_pois = retrieval_svc.load_pois_json(
                os.path.join(snapshot_dir, "pois.json"))
        except (FileNotFoundError, NotADirectoryError):
            all_pois = list(pois_by_id.values())
        candidate_ids = {c["poi_id"]
                         for c in retrieval_svc.retrieve(trip, all_pois)["candidates"]}
        pool = [p for p in all_pois if p.get("poi_id") in candidate_ids]

    travel = ctx.get("travel")
    matrix = (_matrix_from_travel(travel)
              if isinstance(travel, dict) and travel
              else plan.get("matrix") or cells)
    return (plan, trip, pois_by_id, pool, matrix), None


@router.post("/repair")
def repair(body: RepairIn):
    resolved, err = _resolve(body)
    if err is not None:
        return err
    plan, trip, pois_by_id, pool, matrix = resolved

    try:
        result = repair_svc.repair_plan(
            plan, trip, pois_by_id, matrix, pool,
            review_fn=lambda p: review_router.review_plan(p, pois_by_id, trip),
        )
    except Exception as exc:  # noqa: BLE001 - never 500 the harness
        return {"plan": {k: v for k, v in plan.items() if not k.startswith("_")},
                "rounds": 0, "repairs": [], "gate": None,
                "note": f"REPAIR_UNAVAILABLE: {type(exc).__name__}"}

    repaired = {k: v for k, v in result["plan"].items() if not k.startswith("_")}
    return {**result, "plan": repaired}
