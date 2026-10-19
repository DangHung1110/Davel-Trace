"""Multi-profile optimizer runs + solution pool (T032, lane B; US4).

Three weight configs over the T017 optimizer (STUB-NOTE: plain-dict
POIs stand in for T007 schemas, as T017/T018):
- savings: heavy cost penalty (score = -fee/10000 + rating*0.1).
- balanced: pure rating sum.
- experience: rating + intensity (rich experiences first).

Each run -> validate (T018) -> score (total cost, travel time,
preference = mean rating) + profile reason + T032s `scores`
(profit/utility/gate/excluded). Infeasible runs are dropped with a
note (never returned). Output pool: one plan per feasible profile,
each carrying its T032s `scores`; `selected: None` stays the
contract stub (select endpoint is lane C T033e).
"""

from __future__ import annotations

from BE.app.services import response, scorer
from BE.app.services.common import status_map, to_min, total_fee
from BE.app.services.optimizer import (
    StubTrip, optimize, stubs_from_pois)
from BE.app.services.validator import validate

PROFILE_REASONS = {
    "savings": "tiết kiệm: phạt nặng chi phí, ưu tiên điểm rẻ",
    "balanced": "cân bằng: tổng rating cao nhất",
    "experience": "trải nghiệm: ưu tiên rating + hoạt động đậm chất",
}


def _score(profile: str, p: dict) -> float:
    rating, fee = float(p.get("rating") or 0), int(p.get("fee") or 0)
    if profile == "savings":
        return -fee / 10000.0 + rating * 0.1
    if profile == "experience":
        return rating + int(p.get("intensity", 2))
    return rating  # balanced


def score_plan(plan: dict) -> dict:
    """Profit/Utility + gate (T032s, lane B; TravelEval-style).

    profit = preference per million VND (value-for-money; savings wins
    tight budgets). utility = 0.7 preference/5 + 0.3 route efficiency
    (1 - travel_min/600; experience wins preference-heavy asks).
    Gate fail (any constraint_status != 1) -> excluded, scores zeroed.
    """
    gate = bool(plan.get("constraint_status")) and all(
        v == 1 for v in plan["constraint_status"].values())
    if not gate:
        return {"profit": 0.0, "utility": 0.0, "gate": False, "excluded": True}
    pref = float(plan.get("preference", 0.0))
    profit = pref / (1.0 + float(plan.get("total_cost", 0)) / 1000000.0)
    route_eff = max(0.0, 1.0 - float(plan.get("travel_min", 0)) / 600.0)
    utility = 0.7 * (pref / 5.0) + 0.3 * route_eff
    return {"profit": round(profit, 4), "utility": round(utility, 4),
            "gate": True, "excluded": False}


def run_profiles(pois: list[dict], travel: dict[tuple[str, str], int],
                 trip: dict, matrix: dict,
                 profiles: tuple[str, ...] = ("savings", "balanced",
                                              "experience")) -> dict:
    """Run each profile; return {"plans": [...], "dropped": [...], "selected": None}.

    Each plan entry carries its T032s `scores` (profit/utility/gate/
    excluded) attached once the entry is complete.
    """
    plans, dropped = [], []
    by_id = {p["poi_id"]: p for p in pois}
    q = scorer.edge_scores([p["poi_id"] for p in pois], by_id)
    pois_gate = {pid: {"verified": p.get("verified", False), "fee": p.get("fee", 0),
                       "opening_hours": p.get("opening_hours", [])}
                 for pid, p in by_id.items()}
    for prof in profiles:
        stub = stubs_from_pois(pois, trip, lambda p: _score(prof, p))
        out = optimize(stub, travel, _to_trip(trip), edge_scores=q,
                       must_visit=trip.get("must_visit", []))
        if out["itinerary"] is None:
            dropped.append({"profile": prof, "reason": out.get("reason", "")})
            continue
        acts = out["itinerary"]["activities"]
        rep = validate({"activities": acts}, trip, pois_gate, matrix)
        if not rep["passed"]:
            dropped.append({"profile": prof, "reason": str(rep["violations"])})
            continue
        ratings = [float(by_id[a["poi_id"]].get("rating", 0)) for a in acts]
        travel_min = sum(int((matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {})
                             .get("minutes", 0)) for x, y in zip(acts, acts[1:]))
        entry = {
            "profile": prof,
            "reason": PROFILE_REASONS[prof],
            "itinerary": {"activities": acts},
            "total_cost": total_fee(acts, by_id),
            "travel_min": travel_min,
            "preference": round(sum(ratings) / len(ratings), 3) if ratings else 0.0,
            "constraint_status": status_map(rep["checks"]),
        }
        entry["scores"] = score_plan(entry)  # T032s: attached once complete
        plans.append(entry)
    return {"plans": plans, "dropped": dropped, "selected": None}


def _to_trip(trip: dict, origin_id: str | None = "depot") -> StubTrip:
    return StubTrip(to_min(trip.get("start_time", "07:00")),
                    _deadline(trip), origin_id)


def _deadline(trip: dict) -> int:
    """ETB hard within-day deadline: min(end_time, return_time)."""
    end = to_min(trip.get("end_time", "18:00"))
    rt = trip.get("return_time")
    return min(end, to_min(rt)) if rt else end


def _travel_from_cells(cells: dict, ids: list[str]) -> dict:
    """T061a: matrix cells -> {(a,b): minutes}; a missing cell stays ABSENT (B3)."""
    travel = {}
    for a in ids:
        for b in ids:
            if a == b:
                continue
            cell = cells.get(f"{a}->{b}")
            if cell is not None:
                travel[(a, b)] = int(cell["minutes"])
    return travel


def build_plan(profile: str, trip: dict, ranked: list[dict],
               pois_by_id: dict, cells: dict, workers: int = 0) -> dict:
    """T020/T032 router seam: one profile -> one real plan dict.

    Called by POST /v1/itinerary. Adapts the ranked candidate POIs (T061a),
    runs the T017 optimizer as an OPEN tour (no depot cell in the seed
    matrix — see optimizer T061a note), validates (T018) and shapes the
    response (T019) with per-activity explanations (T042).

    The endpoint still owns `itinerary_id`/`trip_id`/`profile`; this returns
    the plan body those fields are attached to. `workers` is forwarded to
    CP-SAT (0 = default; 1 = deterministic, used by the T053 harness).
    """
    prof = profile if profile in PROFILE_REASONS else "balanced"
    ranked_ids = [r.get("poi_id") for r in ranked]
    ids = [pid for pid in ranked_ids if pid in pois_by_id]
    if not ids:
        ids = list(pois_by_id)
    candidates = [pois_by_id[pid] for pid in ids]

    travel = _travel_from_cells(cells, ids)
    stubs = stubs_from_pois(candidates, trip, lambda p: _score(prof, p),
                            deadline=_deadline(trip))
    q = scorer.edge_scores(ids, pois_by_id)
    out = optimize(stubs, travel, _to_trip(trip, origin_id=None),
                   edge_scores=q, workers=workers,
                   must_visit=trip.get("must_visit", []))

    acts = (out.get("itinerary") or {}).get("activities", [])
    pois_gate = {pid: {"verified": p.get("verified", False),
                       "fee": p.get("fee", 0),
                       "opening_hours": p.get("opening_hours", [])}
                 for pid, p in pois_by_id.items()}
    rep = validate({"activities": acts}, trip, pois_gate, cells)

    plan = response.build_plan(out, rep, trip, pois_by_id, cells,
                               version=1, itinerary_id="plan")
    plan["reason"] = PROFILE_REASONS[prof]
    plan["scores"] = score_plan(plan)
    _attach_explanations(plan, ranked)
    # T061e: replan context (trip/pois/travel) travels with the stored plan
    # so POST /replan can rebuild the rolling state; the itinerary router
    # strips leading-underscore keys from the public response.
    plan["_context"] = {"trip": trip, "pois": candidates, "travel": travel}
    return plan


def _attach_explanations(plan: dict, ranked: list[dict]) -> None:
    """FR-023: every activity carries a grounded explanation (evidence)."""
    reasons = {r.get("poi_id"): (r.get("reasons") or []) for r in ranked}
    for act in plan.get("activities", []):
        pid = act.get("poi_id")
        evidence = list(reasons.get(pid) or []) or [f"seed:{pid}"]
        act["explanation"] = {"claim": f"chon {pid}", "evidence": evidence,
                              "inference": "", "source": "rank"}
