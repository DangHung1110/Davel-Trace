"""POST /v1/itinerary/select (T033e, lane C — closes US4). Chốt plan.

In: {"itinerary_id"}. Out: {"active_id"}. Plan được chọn thành lịch
chính, các plans khác giữ lại để so sánh (STUB-NOTE: in-memory store;
state store runtime + version là lane B T045, wire ở phase-PR).
Unknown id -> 404 envelope (không crash).

T061 wiring: the former `gate_stub` always passed; select now runs the
canonical lane-B registry (`BE.app.services.gate.CHECKS`, 7 checks) over
the plan's real context. Plans built by POST /v1/itinerary carry
`_context = {trip, pois, travel}`; that context is normalised into the
shared `(itinerary, trip, pois, matrix)` plain-dict shape `gate.py` reads.
A plan whose context cannot be rebuilt is left selectable (legacy/stub
plans, e.g. injectable test builders) — never fabricate a gate failure.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.routers import error
from BE.app.services import gate

router = APIRouter(prefix="/v1", tags=["itinerary"])

_STORE: dict = {"plans": {}, "active_id": None, "selected": None, "gate": None}


class SelectIn(BaseModel):
    itinerary_id: str


def register(plans: list[dict]) -> None:
    for p in plans:
        _STORE["plans"][p["itinerary_id"]] = p


def get_store() -> dict:
    return _STORE


def reset_store() -> None:
    _STORE["plans"] = {}
    _STORE["active_id"] = None
    _STORE["selected"] = None
    _STORE["gate"] = None


def _matrix_from_travel(travel: dict) -> dict:
    """{(a, b): minutes} (replan shape) -> {"a->b": {"minutes": n}} (gate shape)."""
    return {f"{a}->{b}": {"minutes": int(minutes)}
            for (a, b), minutes in travel.items()}


def _gate_inputs(plan: dict):
    """Plan -> (itinerary, trip, pois, matrix) for the canonical gate, or None.

    Real plans (POST /v1/itinerary) carry `_context` with trip + pois list +
    travel tuple-map; legacy plans expose the same data as plan fields.
    Returns None when trip/pois are absent, so the caller can skip the gate
    instead of inventing a failure.
    """
    ctx = plan.get("_context") or {}
    trip = ctx.get("trip") or plan.get("trip")
    raw_pois = ctx.get("pois") or plan.get("pois")
    if not trip or not raw_pois:
        return None
    pois = (raw_pois if isinstance(raw_pois, dict)
            else {p["poi_id"]: p for p in raw_pois})
    travel = ctx.get("travel")
    matrix = (_matrix_from_travel(travel)
              if isinstance(travel, dict) and travel else plan.get("matrix") or {})
    itinerary = plan if "activities" in plan else plan.get("itinerary", plan)
    return itinerary, trip, pois, matrix


def evaluate_plan(plan: dict) -> dict | None:
    """Real gate report for one plan: {passed, failed, score, checks, scores}.

    `score` is the finite mean of the seven canonical check scores in [0, 1].
    Returns None when the plan has no gate context to evaluate.
    """
    inputs = _gate_inputs(plan)
    if inputs is None:
        return None
    itinerary, trip, pois, matrix = inputs
    results = {name: fn(itinerary, trip, pois, matrix) for name, fn in gate.CHECKS}
    failed = [name for name, res in results.items() if not res["passed"]]
    score = round(sum(res["score"] for res in results.values()) / len(results), 4)
    return {"passed": not failed, "failed": failed, "score": score,
            "checks": {name: res["passed"] for name, res in results.items()},
            "scores": {name: res["score"] for name, res in results.items()}}


@router.post("/itinerary/select")
def select(body: SelectIn):
    if body.itinerary_id not in _STORE["plans"]:
        return error("UNKNOWN_ITINERARY",
                     f"khong co plan {body.itinerary_id}", 404)

    report = evaluate_plan(_STORE["plans"][body.itinerary_id])
    if report is not None and not report["passed"]:
        failed = ", ".join(report["failed"])
        return error("GATE_FAILED",
                     f"plan {body.itinerary_id} khong qua cong: {failed}", 422)

    _STORE["active_id"] = body.itinerary_id
    _STORE["selected"] = body.itinerary_id
    _STORE["gate"] = report
    return {"active_id": body.itinerary_id}
