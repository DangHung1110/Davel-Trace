"""Response builder (T019, lane B). Optimizer output + validator result
-> POST /itinerary plan per contracts/api.md: itinerary + totals
(total cost/km/minutes) + constraint status + version.

STUB-NOTE (as T017/T018): plain-dict inputs matching the plan schemas;
phase-PR swaps the real schemas in. Multi-profile pooling is T032 —
this builds ONE plan; `version` threads through replan (T046) later.
"""

from __future__ import annotations

import time

from BE.app.services.common import status_map, to_min, total_fee


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
    visit_min = sum(to_min(a["end"]) - to_min(a["start"]) for a in acts)
    return {
        "itinerary_id": itinerary_id,
        "trip_id": trip.get("trip_id", "t1"),
        "version": version,
        "activities": acts,
        "segments": segments,
        "total_cost": total_fee(acts, pois),
        "total_km": round(total_km, 2),
        "total_min": visit_min + travel_min,
        "constraint_status": status_map(validation.get("checks", {})),
        "violations": validation.get("violations", []),
        "passed": validation.get("passed", False),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
