"""POST /v1/itinerary (T020, lane C). TripRequest -> plans.

Pipeline: retrieval (real, T015) -> rank (real, T016) -> optimize /
validate / respond (STUB below, clearly marked; lane-B T017/T018/T019
services replace them at phase-PR — same plan shape).

Out per contracts/api.md: {"plans": [...], "selected": None}.
Snapshot missing -> structured error (no crash). Multi-plan is T032.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.config import get_settings
from BE.app.routers import error
from BE.app.schemas.trip import TripRequest
from BE.app.services import rank as rank_svc
from BE.app.services import retrieval as retrieval_svc
from BE.app.services import to_min

router = APIRouter(prefix="/v1", tags=["itinerary"])


class ItineraryIn(BaseModel):
    trip: TripRequest
    profiles: list[str] = ["balanced"]


def _hh(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


# ponytail: lane-B optimizer/validator/responder replaces this stub at phase-PR.
# --- STUB (lane B T017/T018/T019) — deleted at phase-PR ---
def _stub_optimize(ranked: list[dict], by_id: dict, cells: dict,
                   trip: TripRequest) -> list[dict]:
    ws = to_min(trip.start_time)
    acts, cur, prev = [], ws, None
    for r in ranked:
        p = by_id[r["poi_id"]]
        if prev is not None:
            cur += int((cells.get(f"{prev}->{p['poi_id']}", {}) or {}).get("minutes", 0))
        dur = int((p.get("visit_min") or {}).get("p50", 60))
        if cur + dur > to_min(trip.end_time):
            break
        hours = p.get("opening_hours", [])
        s = _hh(cur)
        e = _hh(cur + dur)
        if hours and not any(h.split("-")[0] <= s and e <= h.split("-")[1] for h in hours):
            continue
        acts.append({"poi_id": p["poi_id"], "start": s, "end": e,
                     "explanation": {"evidence": ["stub:rank-order"]}})
        prev, cur = p["poi_id"], cur + dur
    return acts


def _stub_validate(acts: list[dict], trip: TripRequest, by_id: dict) -> dict:
    checks = {"FAR": True, "VROH": True, "B3": True, "BCS": True}
    if any(a["poi_id"] not in by_id or not by_id[a["poi_id"]].get("verified")
           for a in acts):
        checks["FAR"] = False
    cost = sum(int(by_id[a["poi_id"]].get("fee", 0)) for a in acts if a["poi_id"] in by_id)
    if cost > trip.budget:
        checks["BCS"] = False
    return checks


def _stub_respond(acts: list[dict], checks: dict, cells: dict,
                  by_id: dict, trip: TripRequest) -> dict:
    km = sum(float((cells.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {}).get("km", 0.0))
             for x, y in zip(acts, acts[1:]))
    visit = sum(to_min(a["end"]) - to_min(a["start"]) for a in acts)
    travel = sum(int((cells.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {}).get("minutes", 0))
                 for x, y in zip(acts, acts[1:]))
    return {"itinerary_id": "it-stub-1", "trip_id": "t1", "version": 1,
            "activities": acts, "total_cost": sum(int(by_id[a["poi_id"]].get("fee", 0)) for a in acts),
            "total_km": round(km, 2), "total_min": visit + travel,
            "constraint_status": {k: (1 if v else 0) for k, v in checks.items()},
            "passed": all(checks.values())}
# --- end STUB ---


@router.post("/itinerary")
def itinerary(body: ItineraryIn):
    settings = get_settings()
    try:
        pois = retrieval_svc.load_pois_json(settings.snapshot_dir + "/pois.json")
    except (FileNotFoundError, NotADirectoryError):
        return error("SNAPSHOT_MISSING",
                     f"snapshot dir {settings.snapshot_dir} chua co (doi lane A T003b)", 503)
    trip = body.trip.model_dump()
    user = {"budget": trip["budget"]}
    by_id = {p["poi_id"]: p for p in pois}
    result = retrieval_svc.retrieve(trip, pois)
    cand_ids = [c["poi_id"] for c in result["candidates"]]
    ranked = rank_svc.rank([by_id[i] for i in cand_ids], user,
                           {"trip": trip, "hour": trip["start_time"]})
    cells = {}
    try:
        import json
        with open(settings.snapshot_dir + "/matrix.json", encoding="utf-8") as f:
            cells = json.load(f)["cells"]
    except (FileNotFoundError, NotADirectoryError):
        cells = {}
    acts = _stub_optimize(ranked, by_id, cells, body.trip)
    if not acts:
        return error("NO_FEASIBLE_PLAN",
                     "khong co lich kha thi, thu noi soft (FR-022)", 422)
    checks = _stub_validate(acts, body.trip, by_id)
    if not all(checks.values()):
        return error("NO_FEASIBLE_PLAN",
                     f"rot cong {[k for k, v in checks.items() if not v]}", 422)
    return {"plans": [_stub_respond(acts, checks, cells, by_id, body.trip)],
            "selected": None}
