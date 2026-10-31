"""Tier-1 deterministic metrics (T049, lane A; converged at T061f). No LLM.

T061f single-source: the concrete gate checks live in `BE.app.services.gate`
(`CHECKS`) and are imported here; this module no longer carries copies of
the FAR/VROH/B3/BCS/ETB/TCS/HCS formulas. The public metric wrappers below
read the canonical `score` (compliance in [0,1]); `evaluate` reads `passed`.

Inputs (plain dicts):
  itinerary: {"activities": [{"poi_id", "start", "end", "explanation": ...}],
               "total_cost": int (optional)}
  trip: {"budget": int, "start_time", "end_time", "return_time" (optional),
         "must_visit": [ids], "avoid": [ids], "order_prefs": [[a, b], ...]}
  pois: {poi_id: POI snapshot dict} (opening_hours, fee, rating, verified)
  matrix: {"a->b": {"minutes": int}} (OSRM cache; never haversine here)

Gate (FR-035): FAR=0, VROH=0, B3=0, BCS=1, TCS=1, HCS=1. `evaluate` returns
soft scores ONLY when the gate passes (contracts/api.md).
"""

from __future__ import annotations

from BE.app.services.gate import (
    CHECKS as GATE_CHECKS,
    SOFT_CHECKS,
    check_b3,
    check_bcs,
    check_far,
    check_hcs,
    check_tcs,
    check_vroh,
)
from BE.common import deadline, party_size, plan_cost, to_min

__all__ = ["GATE_CHECKS", "evaluate", "far", "vroh", "bcs", "tcs", "hcs",
           "str_score", "dtu", "ssr", "csm", "edi", "aqe"]


def _acts(itinerary: dict) -> list[dict]:
    return itinerary.get("activities", [])


# --- gate-shaped metrics (delegates to the canonical checks' score) --------

def far(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Failed Activity Ratio = 1 - (verified score). Empty plan -> 1.0."""
    return 1.0 - check_far(itinerary, trip, pois, matrix)["score"]


def vroh(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Violation Rate of Opening Hours = 1 - compliant score."""
    return 1.0 - check_vroh(itinerary, trip, pois, matrix)["score"]


def bcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> int:
    """Budget Constraint Satisfaction = 1 if total cost <= budget else 0."""
    return int(check_bcs(itinerary, trip, pois, matrix)["score"] >= 1.0)


def tcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Time Constraint Satisfaction (canonical mirror + overlap/window)."""
    return check_tcs(itinerary, trip, pois, matrix)["score"]


def hcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Hard Constraint Satisfaction (canonical mirror + must/avoid)."""
    return check_hcs(itinerary, trip, pois, matrix)["score"]


def str_score(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Spatio-Temporal Reachability = B3 compliant-transition ratio."""
    return check_b3(itinerary, trip, pois, matrix)["score"]


# --- soft quality metrics (only returned when the gate passes) ------------

def dtu(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Daily Time Utilization = visit minutes / available minutes (0..1)."""
    total = sum(to_min(a["end"]) - to_min(a["start"]) for a in _acts(itinerary))
    days = len({a.get("day") for a in _acts(itinerary)}) or 1
    avail = (deadline(trip) - to_min(trip["start_time"])) * days
    return max(0.0, min(1.0, total / avail)) if avail > 0 else 0.0


def ssr(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Sequence Satisfaction Rate = fraction of order_prefs (a before b)."""
    prefs = trip.get("order_prefs", [])
    if not prefs:
        return 1.0
    pos = {a.get("poi_id"): i for i, a in
           enumerate(sorted(_acts(itinerary), key=lambda a: (a.get("day") or 1, a["start"])))}
    ok = sum(a in pos and b in pos and pos[a] < pos[b] for a, b in prefs)
    return ok / len(prefs)


def csm(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Cost-Spend Margin = budget headroom ratio in [0,1] (1 = free trip)."""
    budget = int(trip.get("budget", 0))
    if budget <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - plan_cost(itinerary, pois, party_size(trip)) / budget))


def edi(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Evidence Density Index = fraction of activities with >=1 evidence."""
    acts = _acts(itinerary)
    if not acts:
        return 0.0
    ok = sum(1 for a in acts if (a.get("explanation") or {}).get("evidence"))
    return ok / len(acts)


def aqe(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Attraction Quality Estimate = mean POI rating / 5 (0..1)."""
    ratings = [pois[a["poi_id"]].get("rating") for a in _acts(itinerary)
               if a.get("poi_id") in pois and pois[a["poi_id"]].get("rating")]
    return (sum(ratings) / len(ratings) / 5.0) if ratings else 0.0


def evaluate(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Gate first (named HARD violations), soft scores only when passed.

    F1 lives in the shared registry but is a SOFT quota: it is deliberately
    excluded from `gate.violations` (contract shape stays 2 keys) so an
    all-food day still gets soft scores.
    """
    violations = [name for name, fn in GATE_CHECKS
                  if name not in SOFT_CHECKS
                  and not fn(itinerary, trip, pois, matrix)["passed"]]
    gate = {"passed": not violations, "violations": violations}
    soft: dict = {}
    if gate["passed"]:
        soft = {"STR": str_score(itinerary, trip, pois, matrix),
                "DTU": round(dtu(itinerary, trip, pois, matrix), 3),
                "SSR": ssr(itinerary, trip, pois, matrix),
                "CSM": round(csm(itinerary, trip, pois, matrix), 3),
                "EDI": edi(itinerary, trip, pois, matrix),
                "AQE": round(aqe(itinerary, trip, pois, matrix), 3)}
    return {"gate": gate, "soft": soft}
