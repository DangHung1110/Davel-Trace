"""Validator gate (T018, lane B). Per-gate pass/fail + violations.

Wraps gate.py (T011) primitives for optimizer output (T017) and, later,
the evaluator endpoint (T052): {"passed", "checks": {FAR/VROH/B3/BCS/ETB},
"violations": [...], "details": {gate: [offending poi_ids]}}.

STUB-NOTE (as T017): inputs are plain dicts matching the plan schemas;
phase-PR swaps in the real schemas (T007 plan.py) without changing this
logic. Matrix comes from T010 (dict cells here).
"""

from __future__ import annotations

from BE.app.services.common import in_range, to_min, total_fee
from BE.app.services.gate import CHECKS


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
    return []


def validate(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    checks = {name: bool(fn(itinerary, trip, pois, matrix)) for name, fn in CHECKS}
    violations = [name for name, ok in checks.items() if not ok]
    return {"passed": not violations, "checks": checks, "violations": violations,
            "details": {name: _offenders(name, itinerary, trip, pois, matrix)
                        for name in violations}}
