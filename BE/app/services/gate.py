"""Gate primitives (T011, lane B). Shared booleans for validator + evaluator.

- FAR: no activity on unknown/unverified POI (FR-013).
- VROH: no activity outside POI opening hours (SC-006).
- B3: no Broken transit Buffer — every consecutive transition's gap
  fits the matrix travel minutes (research R4: haversine-only breaks
  B3 feasibility, hence T010's no-guess rule).
- BCS: total cost within budget (SC-008).
- ETB: the last activity ends by trip end_time and, when present, return_time.

Self-contained (lane-B worktree has no BE/eval yet — lanes.md STUB
rule): formulas mirror lane-A `BE/eval/metrics.py` ratios as booleans;
validator T018 uses `all_pass()`; evaluator converges at phase-PR.
Inputs are the same plain dicts as T049 (itinerary/trip/pois/matrix).
"""

from __future__ import annotations

from BE.app.services.common import in_range, to_min, total_fee


def check_far(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> bool:
    """True iff every activity references a known AND verified POI."""
    acts = itinerary.get("activities", [])
    return bool(acts) and all(a.get("poi_id") in pois
                              and pois[a["poi_id"]].get("verified") for a in acts)


def check_vroh(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> bool:
    """True iff every activity fits its POI opening hours."""
    for a in itinerary.get("activities", []):
        hours = (pois.get(a.get("poi_id"), {}) or {}).get("opening_hours") or []
        s, e = to_min(a["start"]), to_min(a["end"])
        if hours and not any(in_range(s, e, h) for h in hours):
            return False
    return True


def check_b3(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> bool:
    """True iff every transition gap fits matrix travel minutes (B3=0)."""
    acts = sorted(itinerary.get("activities", []), key=lambda a: a["start"])
    for x, y in zip(acts, acts[1:]):
        gap = to_min(y["start"]) - to_min(x["end"])
        need = (matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {}).get("minutes")
        if need is None or gap < need:
            return False
    return True


def check_bcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> bool:
    """True iff total cost is within budget."""
    if "total_cost" in itinerary:
        cost = int(itinerary["total_cost"])
    else:
        cost = total_fee(itinerary.get("activities", []), pois)
    return cost <= int(trip.get("budget", 0))


def check_etb(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> bool:
    """True iff the last activity ends by each configured trip deadline."""
    acts = itinerary.get("activities", [])
    deadlines = [to_min(value) for value in
                 (trip.get("end_time"), trip.get("return_time")) if value]
    if not acts or not deadlines:
        return True
    last_end = max(to_min(a["end"]) for a in acts)
    return last_end <= min(deadlines)


CHECKS = (("FAR", check_far), ("VROH", check_vroh),
          ("B3", check_b3), ("BCS", check_bcs), ("ETB", check_etb))


def all_pass(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """{"passed": bool, "failed": [names]} — validator T018 entry point."""
    failed = [name for name, fn in CHECKS
              if not fn(itinerary, trip, pois, matrix)]
    return {"passed": not failed, "failed": failed}
