"""Multi-profile optimizer runs + solution pool (T032, lane B; US4).

Three weight configs over the T017 optimizer (STUB-NOTE: plain-dict
POIs stand in for T007 schemas, as T017/T018):
- savings: heavy cost penalty (score = -fee/10000 + rating*0.1).
- balanced: pure rating sum.
- experience: rating + intensity (rich experiences first).

Each run -> validate (T018) -> score (total cost, travel time,
preference = mean rating) + profile reason. Infeasible runs are
dropped with a note (never returned). Output pool: one plan per
feasible profile, `selected: None` (select endpoint is lane C T033e).
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.app.services.validator import validate  # noqa: E402

PROFILE_REASONS = {
    "savings": "tiết kiệm: phạt nặng chi phí, ưu tiên điểm rẻ",
    "balanced": "cân bằng: tổng rating cao nhất",
    "experience": "trải nghiệm: ưu tiên rating + hoạt động đậm chất",
}


def _score(profile: str, p: dict) -> float:
    rating, fee = float(p.get("rating", 0)), int(p.get("fee", 0))
    if profile == "savings":
        return -fee / 10000.0 + rating * 0.1
    if profile == "experience":
        return rating + int(p.get("intensity", 2))
    return rating  # balanced


def _mm(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


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


def _hh(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _win(p: dict, trip: dict) -> tuple[int, int]:
    hours = p.get("opening_hours", [])
    if hours:
        o, c = hours[0].split("-")
        return _mm(o), _mm(c)
    return _mm(trip.get("start_time", "07:00")), _mm(trip.get("end_time", "18:00"))


def run_profiles(pois: list[dict], travel: dict[tuple[str, str], int],
                 trip: dict, matrix: dict,
                 profiles: tuple[str, ...] = ("savings", "balanced",
                                              "experience")) -> dict:
    """Run each profile; return {"plans": [...], "dropped": [...], "selected": None}."""
    plans, dropped = [], []
    for prof in profiles:
        stub = [StubPOI(p["poi_id"], int(p.get("visit_min", 60)),
                        *_win(p, trip), _score(prof, p)) for p in pois]
        out = optimize(stub, travel, _to_trip(trip))
        if out["itinerary"] is None:
            dropped.append({"profile": prof, "reason": out.get("reason", "")})
            continue
        acts = out["itinerary"]["activities"]
        rep = validate({"activities": acts}, trip,
                       {p["poi_id"]: {"verified": True,
                                      "fee": p.get("fee", 0),
                                      "opening_hours": p.get("opening_hours", [])}
                        for p in pois}, matrix)
        if not rep["passed"]:
            dropped.append({"profile": prof, "reason": str(rep["violations"])})
            continue
        ratings = [float(next(p for p in pois if p["poi_id"] == a["poi_id"])
                         .get("rating", 0)) for a in acts]
        travel_min = sum(int((matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {})
                             .get("minutes", 0)) for x, y in zip(acts, acts[1:]))
        plans.append({
            "profile": prof,
            "reason": PROFILE_REASONS[prof],
            "itinerary": {"activities": acts},
            "total_cost": sum(int(next(p for p in pois if p["poi_id"] == a["poi_id"])
                                  .get("fee", 0)) for a in acts),
            "travel_min": travel_min,
            "preference": round(sum(ratings) / len(ratings), 3) if ratings else 0.0,
            "constraint_status": {k: (1 if v else 0) for k, v in rep["checks"].items()},
        })
    return {"plans": plans, "dropped": dropped, "selected": None}


def _to_trip(trip: dict) -> StubTrip:
    return StubTrip(_mm(trip.get("start_time", "07:00")),
                    _mm(trip.get("end_time", "18:00")))
