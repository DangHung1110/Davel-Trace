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


def _legs(acts: list[dict], origin: str | None) -> list[tuple[str, str]]:
    """The drives of a plan: stop to stop, and from the base to each day's first stop
    when the trip starts at one (a day never starts where the last one ended)."""
    legs = []
    for i, act in enumerate(acts):
        new_day = i == 0 or act.get("day") != acts[i - 1].get("day")
        if new_day and origin:
            legs.append((origin, act["poi_id"]))
        elif i > 0:
            legs.append((acts[i - 1]["poi_id"], act["poi_id"]))
    return legs


def plan_totals(acts: list[dict], trip: dict, pois: dict, matrix: dict) -> dict:
    """Everything a plan derives from its stops: route, money, minutes, mean rating."""
    segments, total_km, travel_min = [], 0.0, 0
    for a, b in _legs(acts, trip.get("origin_id")):
        cell = (matrix.get(f"{a}->{b}", {}) or {})
        km, minutes = float(cell.get("km", 0.0)), int(cell.get("minutes", 0))
        # "cache": the matrix's own leg; "gps_estimate": the first leg of a day that
        # starts at a GPS fix (matrix.with_starts).
        segments.append({"from_id": a, "to_id": b,
                         "mode": "motorbike", "km": km, "minutes": minutes,
                         "source": cell.get("source") or "cache"})
        total_km += km
        travel_min += minutes
    visit_min = sum(to_min(a["end"]) - to_min(a["start"]) for a in acts)
    ratings = [trusted_rating(pois.get(a["poi_id"]) or {}) for a in acts]
    return {"segments": segments,
            "total_cost": total_fee(acts, pois, party_size(trip)),
            # FR-026: part of total_cost is a guess (a price no source checked).
            # Here, not in build_plan, so a repaired plan says it of its new stops.
            "cost_estimated": any(fee_is_estimate(pois.get(a["poi_id"]) or {}) for a in acts),
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
        **plan_totals(acts, trip, pois, matrix),
        "constraint_status": status_map(_hard_checks(validation)),
        "violations": validation.get("violations", []),
        "soft_violations": validation.get("soft_violations", []),
        "passed": validation.get("passed", False),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
