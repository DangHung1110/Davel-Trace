"""POST /v1/itinerary/select (T033e, lane C — closes US4). Chốt plan.

In: {"itinerary_id"}. Out: {"active_id"}. Plan được chọn thành lịch
chính, các plans khác giữ lại để so sánh (STUB-NOTE: in-memory store;
state store runtime + version là lane B T045, wire ở phase-PR).
Unknown id -> 404 envelope (không crash).

T061 wiring: the former `gate_stub` always passed; select now runs the
canonical lane-B registry (`BE.app.services.gate.CHECKS`, 9 checks) over
the plan's real context. Plans built by POST /v1/itinerary carry
`_context = {trip, pois, travel}`; that context is normalised into the
shared `(itinerary, trip, pois, matrix)` plain-dict shape `gate.py` reads.
A plan whose context cannot be rebuilt is left selectable (legacy/stub
plans, e.g. injectable test builders) — never fabricate a gate failure.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from BE.app.config import get_settings
from BE.app.routers import error
from BE.app.services import gate
from BE.app.services.acceptance_store import AcceptanceStore

router = APIRouter(prefix="/v1", tags=["itinerary"])

_STORE: dict = {"plans": {}, "active_id": None, "selected": None, "gate": None}


class SelectIn(BaseModel):
    itinerary_id: str
    idempotency_key: str | None = Field(default=None, min_length=8,
                                        max_length=128)
    parent_acceptance_id: str | None = None


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
    """Real gate report for one plan (gate.report over the plan context).

    `failed` is the HARD fail list (select is fail-closed on it); soft checks
    (F1) land in `soft_failed` and never block selection.
    Returns None when the plan has no gate context to evaluate.
    """
    inputs = _gate_inputs(plan)
    if inputs is None:
        return None
    itinerary, trip, pois, matrix = inputs
    return gate.family_report(itinerary, trip, pois, matrix)


def _public_plan(plan: dict) -> dict:
    return {key: value for key, value in plan.items()
            if not key.startswith("_")}


def _save_acceptance(plan: dict, report: dict, body: SelectIn) -> dict:
    settings = get_settings()
    ctx = plan.get("_context") or {}
    request = ctx.get("trip") or plan.get("trip") or {
        "trip_id": plan.get("trip_id", "")
    }
    key = body.idempotency_key or f"legacy-{uuid4()}"
    return AcceptanceStore(settings.acceptance_db_path).save_acceptance(
        idempotency_key=key,
        itinerary_id=body.itinerary_id,
        trip_id=str(plan.get("trip_id") or request.get("trip_id") or ""),
        parent_acceptance_id=body.parent_acceptance_id,
        data_version=str(plan.get("data_version") or settings.snapshot_name),
        request=request,
        plan=_public_plan(plan),
        gate=report or plan.get("gate") or {"passed": True},
        deterministic_rank=plan.get("deterministic_rank"),
        deterministic_score=plan.get("deterministic_score"),
        shadow_observation_id=(plan.get("shadow") or {}).get("observation_id"),
    )


@router.post("/itinerary/select")
def select(body: SelectIn):
    if body.itinerary_id not in _STORE["plans"]:
        return error("UNKNOWN_ITINERARY",
                     f"khong co plan {body.itinerary_id}", 404)

    plan = _STORE["plans"][body.itinerary_id]
    report = evaluate_plan(plan)
    if report is not None and not report["passed"]:
        failed = ", ".join(report["failed"])
        return error("GATE_FAILED",
                     f"plan {body.itinerary_id} khong qua cong: {failed}", 422)

    # Persistence is part of selection. Save first, then activate; a failed
    # local database write must not claim that a durable choice succeeded.
    try:
        acceptance = _save_acceptance(
            plan, report or plan.get("gate") or {"passed": True}, body)
    except (OSError, ValueError) as exc:
        return error("ACCEPTANCE_STORE_ERROR", str(exc), 503)

    _STORE["active_id"] = body.itinerary_id
    _STORE["selected"] = body.itinerary_id
    _STORE["gate"] = report
    if body.idempotency_key is None:
        # Exact legacy response shape; the server-generated key still creates
        # an immutable record for roadmap data capture.
        return {"active_id": body.itinerary_id}
    return {
        "active_id": body.itinerary_id,
        "acceptance": {
            key: acceptance.get(key)
            for key in (
                "acceptance_id", "itinerary_id", "trip_id", "selected_at",
                "schema_version", "data_version", "parent_acceptance_id",
            )
        },
    }
