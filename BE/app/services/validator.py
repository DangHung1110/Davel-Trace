"""Validator gate (T018, lane B). Per-gate pass/fail + violations.

Wraps gate.py (T011) primitives for optimizer output (T017) and, later,
the evaluator endpoint (T052): {"passed", "checks": {FAR/VROH/B3/BCS/ETB/A1/
CAFE_CAP/NO_CONSECUTIVE/NO_ADJACENT_FOOD/REST_FOLLOWS_LUNCH/F1/TCS/HCS},
"violations": [...], "soft_violations": [...], "details": {gate:
[offending poi_ids]}}.

`violations` stays the HARD fail list (fail-closed); `soft_violations` carries
the quality checks registered in `gate.SOFT_CHECKS` (currently F1) so an
all-food day is reported without making the plan infeasible. `details`
covers both lists.

STUB-NOTE (as T017): inputs are plain dicts matching the plan schemas;
phase-PR swaps in the real schemas (T007 plan.py) without changing this
logic. Matrix comes from T010 (dict cells here).
"""

from __future__ import annotations

from BE.app.services.common import deadline, in_range, to_min, total_fee
from BE.app.services.gate import CHECKS, SOFT_CHECKS, check_cafe_cap
from BE.app.services.soft_rules import (
    CATEGORY_DAILY_CAP,
    NON_FOOD_CAPPED,
    REST_START_TOLERANCE,
    effective_rest,
    is_food,
    is_restaurant,
    is_sightseeing,
    lunch_activity,
    meal_slot,
    poi_category,
    rest_span,
)


def _offenders(gate: str, itinerary: dict, trip: dict, pois: dict,
               matrix: dict) -> list[str]:
    acts = itinerary.get("activities", [])
    if gate == "FAR":
        return [a.get("poi_id") for a in acts
                if a.get("poi_id") not in pois or not pois[a["poi_id"]].get("verified")]
    if gate == "VROH":
        out = []
        for a in acts:
            hours = (pois.get(a.get("poi_id"), {}) or {}).get("opening_hours") or []
            s, e = to_min(a["start"]), to_min(a["end"])
            if hours and not any(in_range(s, e, h) for h in hours):
                out.append(a.get("poi_id"))
        return out
    if gate == "B3":
        out = []
        ordered = sorted(acts, key=lambda a: a["start"])
        for x, y in zip(ordered, ordered[1:]):
            gap = to_min(y["start"]) - to_min(x["end"])
            need = (matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {}).get("minutes")
            if need is None or gap < need:
                out.append(f"{x['poi_id']}->{y['poi_id']}")
        return out
    if gate == "BCS":
        cost = int(itinerary.get("total_cost", total_fee(acts, pois)))
        return [] if cost <= int(trip.get("budget", 0)) else [f"cost {cost}"]
    if gate == "ETB" and acts:
        deadlines = [to_min(value) for value in
                     (trip.get("end_time"), trip.get("return_time")) if value]
        last = max(acts, key=lambda a: to_min(a["end"]))
        if deadlines and to_min(last["end"]) > min(deadlines):
            return [last.get("poi_id")]
    if gate == "A1":
        # Every restaurant in an over-filled meal slot is an offender.
        slots: dict[int, list[str]] = {}
        for a in acts:
            if poi_category(pois.get(a.get("poi_id"), {})) != "restaurant":
                continue
            slot = meal_slot(a["start"])
            if slot is not None:
                slots.setdefault(slot, []).append(a.get("poi_id"))
        return list(dict.fromkeys(poi_id for ids in slots.values()
                                  if len(ids) > 1 for poi_id in ids))
    if gate == "CAFE_CAP":
        # Every cafe is an offender when the day's quota is exceeded: the cap
        # is a day-level budget, not a bad single stop.
        cafes = [a.get("poi_id") for a in acts
                 if poi_category(pois.get(a.get("poi_id"), {})) == "cafe"]
        if check_cafe_cap(itinerary, trip, pois, matrix)["passed"]:
            return []
        return list(dict.fromkeys(cafes))
    if gate == "CATEGORY_CAP":
        # Every POI of an over-filled capped category is an offender: the cap
        # is a day-level budget, not one bad stop.
        capped: dict[str, list[str]] = {}
        for a in acts:
            cat = poi_category(pois.get(a.get("poi_id"), {}))
            if cat in NON_FOOD_CAPPED:
                capped.setdefault(cat, []).append(a.get("poi_id"))
        return list(dict.fromkeys(
            poi_id for ids in capped.values()
            if len(ids) > CATEGORY_DAILY_CAP for poi_id in ids))
    if gate == "NO_CONSECUTIVE":
        ordered = sorted(acts, key=lambda a: a["start"])
        out = []
        for x, y in zip(ordered, ordered[1:]):
            left = poi_category(pois.get(x.get("poi_id"), {}))
            right = poi_category(pois.get(y.get("poi_id"), {}))
            if left and left == right:
                out.append(f"{x.get('poi_id')}->{y.get('poi_id')}")
        return out
    if gate == "NO_ADJACENT_FOOD":
        ordered = sorted(acts, key=lambda a: a["start"])
        return [f"{x.get('poi_id')}->{y.get('poi_id')}"
                for x, y in zip(ordered, ordered[1:])
                if is_restaurant(pois.get(x.get("poi_id")))
                and is_restaurant(pois.get(y.get("poi_id")))]
    if gate == "REST_FOLLOWS_LUNCH":
        profile = trip.get("profile") or {}
        if not profile:
            return []
        lunch = lunch_activity(acts, pois)
        if lunch is None:
            return ["khong co bua trua"]
        span = rest_span(acts, pois, profile, deadline(trip))
        declared = effective_rest(span, itinerary.get("rest"))
        lo, hi = declared["start"], declared["end"]
        late = lo - span["lunch_end"]
        if (not 0 <= late <= REST_START_TOLERANCE
                or declared["minutes"] != span["minutes"]):
            return ["cua so nghi trua sai gio/do dai"]
        return [a.get("poi_id") for a in sorted(acts, key=lambda a: a["start"])
                if a is not lunch
                and to_min(a["start"]) < hi and to_min(a["end"]) > lo]
    if gate == "F1":
        # SOFT: list what is missing. No food -> every activity is the
        # offender; food present but no sightseeing -> the food stops are.
        ids = [a.get("poi_id") for a in acts]
        if not any(is_food(pois.get(pid, {})) for pid in ids):
            return ids
        return [pid for pid in ids if is_food(pois.get(pid, {}))]
    if gate in ("TCS", "HCS"):
        mirrors = {
            "TCS": ("VROH", "B3", "ETB"),
            "HCS": ("FAR", "VROH", "B3", "BCS", "ETB", "A1",
                    "CAFE_CAP", "CATEGORY_CAP", "NO_CONSECUTIVE",
                    "NO_ADJACENT_FOOD", "REST_FOLLOWS_LUNCH"),
        }
        return list(dict.fromkeys(
            offender
            for source in mirrors[gate]
            for offender in _offenders(source, itinerary, trip, pois, matrix)
        ))
    return []


def validate(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    checks = {name: fn(itinerary, trip, pois, matrix)["passed"]
              for name, fn in CHECKS}
    failed = [name for name, ok in checks.items() if not ok]
    violations = [name for name in failed if name not in SOFT_CHECKS]
    soft_violations = [name for name in failed if name in SOFT_CHECKS]
    return {"passed": not violations, "checks": checks,
            "violations": violations, "soft_violations": soft_violations,
            "details": {name: _offenders(name, itinerary, trip, pois, matrix)
                        for name in failed}}
