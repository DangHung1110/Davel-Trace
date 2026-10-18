"""Canonical gate primitives (T011, lane B), shared by validator + evaluator.

- FAR: no activity on unknown/unverified POI (FR-013).
- VROH: no activity outside POI opening hours (SC-006).
- B3: no Broken transit Buffer — every consecutive transition's gap
  fits the matrix travel minutes (research R4: haversine-only breaks
  B3 feasibility, hence T010's no-guess rule).
- BCS: total cost within budget (SC-008).
- ETB: the last activity ends by trip end_time and, when present, return_time.
- TCS: time-related mirror over VROH, B3, and ETB.
- HCS: hard-constraint mirror over the five concrete lane-B gates.

Self-contained (lane-B worktree has no BE/eval yet — lanes.md STUB
rule): formulas mirror lane-A `BE/eval/metrics.py` metrics as booleans;
TCS/HCS are local mirrors until the evaluator converges at the T061 wiring
PR. Inputs are the same plain dicts as T049 (itinerary/trip/pois/matrix).
"""

from __future__ import annotations

from BE.app.services.common import in_range, to_min, total_fee


def _result(passed: bool) -> dict:
    """Return the canonical gate result; current boolean mirrors score 0/1."""
    passed = bool(passed)
    return {"passed": passed, "score": 1.0 if passed else 0.0}


def check_far(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Return the canonical result; pass iff every activity uses a verified POI."""
    acts = itinerary.get("activities", [])
    passed = bool(acts) and all(a.get("poi_id") in pois
                                and pois[a["poi_id"]].get("verified") for a in acts)
    return _result(passed)


def check_vroh(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Return the canonical result; pass iff every activity fits opening hours."""
    for a in itinerary.get("activities", []):
        hours = (pois.get(a.get("poi_id"), {}) or {}).get("opening_hours") or []
        s, e = to_min(a["start"]), to_min(a["end"])
        if hours and not any(in_range(s, e, h) for h in hours):
            return _result(False)
    return _result(True)


def check_b3(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Return the canonical result; pass iff each gap fits matrix travel time."""
    acts = sorted(itinerary.get("activities", []), key=lambda a: a["start"])
    for x, y in zip(acts, acts[1:]):
        gap = to_min(y["start"]) - to_min(x["end"])
        need = (matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {}).get("minutes")
        if need is None or gap < need:
            return _result(False)
    return _result(True)


def check_bcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Return the canonical result; pass iff total cost is within budget."""
    if "total_cost" in itinerary:
        cost = int(itinerary["total_cost"])
    else:
        cost = total_fee(itinerary.get("activities", []), pois)
    return _result(cost <= int(trip.get("budget", 0)))


def check_etb(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Return the canonical result; return_time is a hard within-day deadline.

    When both deadlines are present, the earlier of end_time and return_time
    applies; an evening extension must be a new plan and re-gated.
    """
    acts = itinerary.get("activities", [])
    deadlines = [to_min(value) for value in
                 (trip.get("end_time"), trip.get("return_time")) if value]
    if not acts or not deadlines:
        return _result(True)
    last_end = max(to_min(a["end"]) for a in acts)
    return _result(last_end <= min(deadlines))


def check_tcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Lane-B TCS mirror: VROH, B3, and ETB must all pass.

    This boolean stub follows lanes.md; the evaluator becomes the converged
    implementation at the T061 wiring PR.
    """
    passed = all(check(itinerary, trip, pois, matrix)["passed"]
                 for check in (check_vroh, check_b3, check_etb))
    return _result(passed)


def check_hcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Lane-B HCS mirror: all five concrete lane-B hard gates must pass.

    This boolean stub follows lanes.md; the evaluator becomes the converged
    implementation at the T061 wiring PR.
    """
    passed = all(check(itinerary, trip, pois, matrix)["passed"]
                 for check in (check_far, check_vroh, check_b3,
                               check_bcs, check_etb))
    return _result(passed)


CHECKS = (("FAR", check_far), ("VROH", check_vroh),
          ("B3", check_b3), ("BCS", check_bcs), ("ETB", check_etb),
          ("TCS", check_tcs), ("HCS", check_hcs))


def all_pass(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Compatibility summary: {"passed": bool, "failed": [canonical names]}."""
    failed = [name for name, fn in CHECKS
              if not fn(itinerary, trip, pois, matrix)["passed"]]
    return {"passed": not failed, "failed": failed}
