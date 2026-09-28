"""Validator gate (T018, lane B). Per-gate pass/fail + violations.

Wraps gate.py (T011) primitives for optimizer output (T017) and, later,
the evaluator endpoint (T052): {"passed", "checks": {FAR/VROH/B3/BCS},
"violations": [...], "details": {gate: [offending poi_ids]}}.

STUB-NOTE (as T017): inputs are plain dicts matching the plan schemas;
phase-PR swaps in the real schemas (T007 plan.py) without changing this
logic. Matrix comes from T010 (dict cells here).
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.services.gate import CHECKS  # noqa: E402


def _to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


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
            s, e = _to_min(a["start"]), _to_min(a["end"])
            hit = False
            for h in hours:
                o, c = h.split("-")
                o, c = _to_min(o), _to_min(c)
                ok = (o <= s and e <= c) if o <= c else (s >= o or e <= c)
                hit = hit or ok
            if hours and not hit:
                out.append(a.get("poi_id"))
        return out
    if gate == "B3":
        out = []
        ordered = sorted(acts, key=lambda a: a["start"])
        for x, y in zip(ordered, ordered[1:]):
            gap = _to_min(y["start"]) - _to_min(x["end"])
            need = (matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {}).get("minutes")
            if need is None or gap < need:
                out.append(f"{x['poi_id']}->{y['poi_id']}")
        return out
    if gate == "BCS":
        cost = int(itinerary.get("total_cost", sum(
            int((pois.get(a.get("poi_id"), {}) or {}).get("fee", 0)) for a in acts)))
        return [] if cost <= int(trip.get("budget", 0)) else [f"cost {cost}"]
    return []


def validate(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    checks = {name: bool(fn(itinerary, trip, pois, matrix)) for name, fn in CHECKS}
    violations = [name for name, ok in checks.items() if not ok]
    return {"passed": not violations, "checks": checks, "violations": violations,
            "details": {name: _offenders(name, itinerary, trip, pois, matrix)
                        for name in violations}}
