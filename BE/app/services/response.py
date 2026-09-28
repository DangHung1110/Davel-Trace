"""Response builder (T019, lane B). Optimizer output + validator result
-> POST /itinerary plan per contracts/api.md: itinerary + totals
(total cost/km/minutes) + constraint status + version.

STUB-NOTE (as T017/T018): plain-dict inputs matching the plan schemas;
phase-PR swaps the real schemas in. Multi-profile pooling is T032 —
this builds ONE plan; `version` threads through replan (T046) later.
"""

from __future__ import annotations

import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def build_plan(optimizer_out: dict, validation: dict, trip: dict,
               pois: dict, matrix: dict, version: int = 1,
               itinerary_id: str = "it1") -> dict:
    """Wrap one optimizer result + its validation into a plan response."""
    acts = (optimizer_out.get("itinerary") or {}).get("activities", [])
    segments, total_km, travel_min = [], 0.0, 0
    for x, y in zip(acts, acts[1:]):
        cell = (matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {})
        km, minutes = float(cell.get("km", 0.0)), int(cell.get("minutes", 0))
        segments.append({"from_id": x["poi_id"], "to_id": y["poi_id"],
                         "mode": "motorbike", "km": km, "minutes": minutes,
                         "source": "cache"})
        total_km += km
        travel_min += minutes
    visit_min = sum(_to_min(a["end"]) - _to_min(a["start"]) for a in acts)
    total_cost = sum(int((pois.get(a.get("poi_id"), {}) or {}).get("fee", 0))
                     for a in acts)
    checks = validation.get("checks", {})
    return {
        "itinerary_id": itinerary_id,
        "trip_id": trip.get("trip_id", "t1"),
        "version": version,
        "activities": acts,
        "segments": segments,
        "total_cost": total_cost,
        "total_km": round(total_km, 2),
        "total_min": visit_min + travel_min,
        "constraint_status": {k: (1 if v else 0) for k, v in checks.items()},
        "violations": validation.get("violations", []),
        "passed": validation.get("passed", False),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
