"""Tier-1 deterministic metrics (T049, lane A). No LLM, no learned weights.

Inputs (plain dicts; Pydantic wiring is lane C T007, validator lane B T011
reuses these primitives via gate.py):
  itinerary: {"activities": [{"poi_id", "start": "HH:MM", "end": "HH:MM",
               "explanation": {"evidence": [...]}}], "total_cost": int (optional)}
  trip: {"budget": int, "start_time": "HH:MM", "end_time": "HH:MM",
         "must_visit": [ids], "avoid": [ids], "order_prefs": [[a, b], ...]}
  pois: {poi_id: POI snapshot dict} (opening_hours, fee, rating, verified)
  matrix: {"a->b": {"minutes": int}} (OSRM cache; never haversine here)

Gate (FR-035, data-model.md): FAR=0, VROH=0, BCS=1, TCS=1, HCS=1.
`evaluate` returns soft scores ONLY when the gate passes (contracts/api.md).
"""

from __future__ import annotations

from BE.common import to_min


def _in_range(start: int, end: int, spec: str) -> bool:
    o, c = spec.split("-")
    o, c = to_min(o), to_min(c)
    if o <= c:
        return o <= start and end <= c
    return start >= o or end <= c  # overnight range


def _acts(itinerary: dict) -> list[dict]:
    return itinerary.get("activities", [])


def _cost(itinerary: dict, pois: dict) -> int:
    if "total_cost" in itinerary:
        return int(itinerary["total_cost"])
    return sum(int(pois.get(a.get("poi_id"), {}).get("fee", 0)) for a in _acts(itinerary))


def far(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Failed Activity Ratio = activities on unknown/unverified POIs / n.

    FR-013: unverified POIs must not enter the main plan. Gate needs 0.
    """
    acts = _acts(itinerary)
    if not acts:
        return 1.0
    bad = sum(1 for a in acts
              if a.get("poi_id") not in pois or not pois[a["poi_id"]].get("verified"))
    return bad / len(acts)


def vroh(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Violation Rate of Opening Hours = activities outside POI hours / n.

    SC-006: must be 0 on tasks with complete data. Gate needs 0.
    """
    acts = _acts(itinerary)
    if not acts:
        return 0.0
    bad = 0
    for a in acts:
        p = pois.get(a.get("poi_id"), {})
        hours = p.get("opening_hours") or []
        s, e = to_min(a["start"]), to_min(a["end"])
        if hours and not any(_in_range(s, e, h) for h in hours):
            bad += 1
    return bad / len(acts)


def bcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> int:
    """Budget Constraint Satisfaction = 1 if total cost <= budget else 0.

    SC-008: 0 violations when budget is a hard constraint. Gate needs 1.
    """
    return 1 if _cost(itinerary, pois) <= int(trip.get("budget", 0)) else 0


def tcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Time Constraint Satisfaction: no overlaps, all inside trip window.

    Returns 1.0 iff every activity fits [start_time, end_time] and no two
    overlap; else the fraction of pairwise-OK adjacencies. Gate needs 1.
    """
    acts = _acts(itinerary)
    if not acts:
        return 0.0
    ws, we = to_min(trip["start_time"]), to_min(trip["end_time"])
    ordered = sorted(acts, key=lambda a: a["start"])
    if any(to_min(a["start"]) < ws or to_min(a["end"]) > we or
           to_min(a["end"]) <= to_min(a["start"]) for a in ordered):
        return 0.0
    if len(ordered) == 1:
        return 1.0
    ok = sum(to_min(x["end"]) <= to_min(y["start"])
             for x, y in zip(ordered, ordered[1:]))
    return ok / (len(ordered) - 1)


def hcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Hard Constraint Satisfaction: must_visit all present, avoid absent.

    Returns 1.0 iff satisfied, else 0.0. Gate needs 1.
    """
    ids = [a.get("poi_id") for a in _acts(itinerary)]
    if any(m in ids for m in trip.get("avoid", [])):
        return 0.0
    must = trip.get("must_visit", [])
    if must and not all(m in ids for m in must):
        return 0.0
    return 1.0


def str_score(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Spatio-Temporal Reachability: fraction of transitions whose matrix
    travel minutes fit the gap between consecutive activities."""
    acts = sorted(_acts(itinerary), key=lambda a: a["start"])
    if len(acts) < 2:
        return 1.0
    ok = 0
    for x, y in zip(acts, acts[1:]):
        gap = to_min(y["start"]) - to_min(x["end"])
        need = (matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {}).get("minutes")
        ok += need is not None and gap >= need
    return ok / (len(acts) - 1)


def dtu(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Daily Time Utilization = visit minutes / available minutes (0..1)."""
    total = sum(to_min(a["end"]) - to_min(a["start"]) for a in _acts(itinerary))
    avail = to_min(trip["end_time"]) - to_min(trip["start_time"])
    return max(0.0, min(1.0, total / avail)) if avail > 0 else 0.0


def ssr(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Sequence Satisfaction Rate = fraction of order_prefs (a before b)
    respected by activity order. SC-004 preference side."""
    prefs = trip.get("order_prefs", [])
    if not prefs:
        return 1.0
    pos = {a.get("poi_id"): i for i, a in
           enumerate(sorted(_acts(itinerary), key=lambda a: a["start"]))}
    ok = sum(a in pos and b in pos and pos[a] < pos[b] for a, b in prefs)
    return ok / len(prefs)


def csm(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Cost-Spend Margin = budget headroom ratio in [0,1] (1 = free trip)."""
    budget = int(trip.get("budget", 0))
    if budget <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - _cost(itinerary, pois) / budget))


def edi(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> float:
    """Evidence Density Index = fraction of activities carrying >=1
    evidence item (SC-012/SC-018 explanation grounding)."""
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


GATE_CHECKS = (
    ("FAR", far, 0.0),
    ("VROH", vroh, 0.0),
    ("BCS", bcs, 1),
    ("TCS", tcs, 1.0),
    ("HCS", hcs, 1.0),
)


def evaluate(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Gate first (named violations), soft scores only when passed."""
    violations = [name for name, fn, want in GATE_CHECKS
                  if fn(itinerary, trip, pois, matrix) != want]
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
