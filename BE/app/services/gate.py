"""Canonical gate registry (T011 + T061f), shared by validator + evaluator.

ONE registry for the seven checks (fixes X8 "2 bộ cổng"): gate.py owns the
formulas, `BE/eval/metrics.py` imports `CHECKS` and reads their `score`.
Every check returns the canonical shape ``{"passed": bool, "score": float}``
with a finite score in [0, 1]:
- FAR: no activity on unknown/unverified POI (FR-013); score = verified
  ratio.
- VROH: no activity outside POI opening hours (SC-006); score = compliant
  ratio.
- B3: no broken transit buffer — every consecutive transition's gap fits
  the matrix travel minutes (R4/B3: a missing cell is infeasible, never
  0/haversine); score = compliant transition ratio.
- BCS: total cost within budget (SC-008).
- ETB: the last activity ends by the deadline = min(end_time, return_time);
  `return_time` is a HARD within-day cap, never silently stretched to
  end_time (an evening extension must be a new, re-gated plan).
- TCS: time mirror — VROH/B3/ETB all pass AND no overlap AND every
  activity fits [start_time, deadline].
- HCS: hard mirror — the five concrete gates pass AND must_visit present
  AND avoid absent.

Inputs are the shared plain dicts (itinerary/trip/pois/matrix) used by the
validator (T049) and the tier-1 evaluator.
"""

from __future__ import annotations

from BE.common import deadline, in_range, plan_cost, to_min

EPS = 1e-9


def _result(passed: bool, score: float | None = None) -> dict:
    """Canonical gate result: passed is a real bool, score a finite float."""
    passed = bool(passed)
    if score is None:
        score = 1.0 if passed else 0.0
    score = max(0.0, min(1.0, float(score)))
    return {"passed": passed, "score": score}


def _ordered(itinerary: dict) -> list[dict]:
    return sorted(itinerary.get("activities", []), key=lambda a: a["start"])


def check_far(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Pass iff every activity uses a verified POI (non-empty plan)."""
    acts = itinerary.get("activities", [])
    if not acts:
        return _result(False, 0.0)
    bad = sum(1 for a in acts
              if a.get("poi_id") not in pois
              or not (pois.get(a["poi_id"]) or {}).get("verified"))
    return _result(bad == 0, 1.0 - bad / len(acts))


def check_vroh(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Pass iff every activity fits opening hours; score = compliant ratio."""
    acts = itinerary.get("activities", [])
    if not acts:
        return _result(True, 1.0)
    bad = 0
    for a in acts:
        hours = (pois.get(a.get("poi_id"), {}) or {}).get("opening_hours") or []
        s, e = to_min(a["start"]), to_min(a["end"])
        if hours and not any(in_range(s, e, h) for h in hours):
            bad += 1
    return _result(bad == 0, 1.0 - bad / len(acts))


def check_b3(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Pass iff each gap fits matrix travel time; score = compliant ratio."""
    acts = _ordered(itinerary)
    if len(acts) < 2:
        return _result(True, 1.0)
    bad = 0
    for x, y in zip(acts, acts[1:]):
        gap = to_min(y["start"]) - to_min(x["end"])
        need = (matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {}).get("minutes")
        if need is None or gap < need:
            bad += 1
    return _result(bad == 0, 1.0 - bad / (len(acts) - 1))


def check_bcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Pass iff total cost is within budget (one formula, both sides)."""
    cost = plan_cost(itinerary, pois)
    return _result(cost <= int(trip.get("budget", 0)))


def check_etb(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """`return_time` is a hard within-day deadline; min(end_time, return_time)."""
    acts = itinerary.get("activities", [])
    if not acts or not (trip.get("end_time") or trip.get("return_time")):
        return _result(True)
    last_end = max(to_min(a["end"]) for a in acts)
    return _result(last_end <= deadline(trip))


def check_tcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Time mirror: VROH/B3/ETB + no overlap + inside [start, deadline]."""
    if not all(check(itinerary, trip, pois, matrix)["passed"]
               for check in (check_vroh, check_b3, check_etb)):
        return _result(False)
    acts = _ordered(itinerary)
    ws, we = to_min(trip.get("start_time", "07:00")), deadline(trip)
    for a in acts:
        s, e = to_min(a["start"]), to_min(a["end"])
        if s < ws or e > we or e <= s:
            return _result(False)
    for x, y in zip(acts, acts[1:]):
        if to_min(x["end"]) > to_min(y["start"]):
            return _result(False)
    return _result(True)


def check_hcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Hard mirror: five concrete gates + must_visit present + avoid absent."""
    if not all(check(itinerary, trip, pois, matrix)["passed"]
               for check in (check_far, check_vroh, check_b3,
                             check_bcs, check_etb)):
        return _result(False)
    ids = [a.get("poi_id") for a in itinerary.get("activities", [])]
    if any(m in ids for m in trip.get("avoid", [])):
        return _result(False)
    must = trip.get("must_visit", [])
    if must and not all(m in ids for m in must):
        return _result(False)
    return _result(True)


CHECKS = (("FAR", check_far), ("VROH", check_vroh),
          ("B3", check_b3), ("BCS", check_bcs), ("ETB", check_etb),
          ("TCS", check_tcs), ("HCS", check_hcs))


def all_pass(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Compatibility summary: {"passed": bool, "failed": [canonical names]}."""
    failed = [name for name, fn in CHECKS
              if not fn(itinerary, trip, pois, matrix)["passed"]]
    return {"passed": not failed, "failed": failed}
