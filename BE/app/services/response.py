"""Response builder (T019, lane B). Optimizer output + validator result
-> POST /itinerary plan per contracts/api.md: itinerary + totals
(total cost/km/minutes) + constraint status + version.
"""

from __future__ import annotations

import time

from BE.app.services.gate import SOFT_CHECKS
from BE.common import fee_is_estimate, party_size, status_map, to_min, total_fee, trusted_rating


def _hard_checks(validation: dict) -> dict:
    """F1 (soft) stays out of constraint_status: it never fail-closes."""
    return {name: ok for name, ok in validation.get("checks", {}).items()
            if name not in SOFT_CHECKS}


def plan_totals(acts: list[dict], trip: dict, pois: dict, matrix: dict) -> dict:
    """Everything a plan derives from its stops: route, money, minutes, mean rating."""
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
    ratings = [trusted_rating(pois.get(a["poi_id"]) or {}) for a in acts]
    return {"segments": segments,
            "total_cost": total_fee(acts, pois, party_size(trip)),
            "total_km": round(total_km, 2),
            "total_min": visit_min + travel_min,
            "travel_min": travel_min,
            "preference": round(sum(ratings) / len(ratings), 3) if ratings else 0.0}


def build_plan(optimizer_out: dict, validation: dict, trip: dict,
               pois: dict, matrix: dict, version: int = 1,
               itinerary_id: str = "it1") -> dict:
    """Wrap one optimizer result + its validation into a plan response."""
    acts = (optimizer_out.get("itinerary") or {}).get("activities", [])
    return {
        "itinerary_id": itinerary_id,
        "trip_id": trip.get("trip_id", "t1"),
        "version": version,
        "activities": acts,
        # FR-026: part of total_cost comes from price bands, not real prices.
        "cost_estimated": any(fee_is_estimate(pois.get(a["poi_id"]) or {}) for a in acts),
        **plan_totals(acts, trip, pois, matrix),
        "constraint_status": status_map(_hard_checks(validation)),
        "violations": validation.get("violations", []),
        "soft_violations": validation.get("soft_violations", []),
        "passed": validation.get("passed", False),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
