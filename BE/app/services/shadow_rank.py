"""Non-authoritative, position-swapped ranking utilities."""

from __future__ import annotations

import hashlib
import json
import math
import time


def stable_canary(trip_id: str, rate: float) -> bool:
    """Stable sample with a hard 10% safety cap; unsafe rates disable it."""
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        return False
    if rate <= 0 or rate > 0.10:
        return False
    bucket = int(hashlib.sha256(str(trip_id).encode()).hexdigest()[:8], 16)
    return (bucket % 10_000) < int(rate * 10_000)


def _facts(plan: dict, candidate_id: str) -> dict:
    activities = [
        {
            "poi_id": item.get("poi_id"),
            "start": item.get("start"),
            "end": item.get("end"),
        }
        for item in plan.get("activities") or []
    ]
    return {
        "candidate_id": candidate_id,
        "activities": activities,
        "total_cost": plan.get("total_cost"),
        "total_km": plan.get("total_km"),
        "total_min": plan.get("total_min"),
        "gate_passed": bool((plan.get("gate") or {}).get("passed", True)),
    }


def anonymize_candidates(plans: list[dict]) -> tuple[list[dict], dict[str, str]]:
    public, mapping = [], {}
    for index, plan in enumerate(plans):
        neutral = chr(ord("A") + index)
        mapping[neutral] = str(plan.get("itinerary_id"))
        public.append(_facts(plan, neutral))
    return public, mapping


def _winner_id(decision: dict, mapping: dict[str, str]) -> str | None:
    winner = str((decision or {}).get("winner") or "").strip().upper()
    return mapping.get(winner)


def consensus(forward: dict, reverse: dict,
              forward_mapping: dict[str, str],
              reverse_mapping: dict[str, str]) -> dict:
    left = _winner_id(forward, forward_mapping)
    right = _winner_id(reverse, reverse_mapping)
    agreed = left is not None and left == right
    return {
        "winner_id": left if agreed else None,
        "swap_consistent": agreed,
        "status": "win" if agreed else "tie",
        "forward_winner_id": left,
        "reverse_winner_id": right,
    }


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    dx, dy = [x - mx for x in xs], [y - my for y in ys]
    denom = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return None if denom == 0 else round(sum(a*b for a, b in zip(dx, dy)) / denom, 4)


def evaluate(plans: list[dict], trip_id: str, data_version: str,
             judge) -> dict:
    """Evaluate both orders. `judge` receives anonymized facts and returns winner."""
    started = time.perf_counter()
    forward, forward_mapping = anonymize_candidates(plans)
    reversed_plans = list(reversed(plans))
    reverse, reverse_mapping = anonymize_candidates(reversed_plans)
    base = {
        "trip_id": trip_id,
        "data_version": data_version,
        "candidate_ids": [str(p.get("itinerary_id")) for p in plans],
        "deterministic_top_id": str(plans[0].get("itinerary_id")) if plans else None,
        "veto_count": 0,
        "authoritative": False,
    }
    try:
        first = judge(forward)
        second = judge(reverse)
        agreed = consensus(first, second, forward_mapping, reverse_mapping)
        ranks = list(range(1, len(plans) + 1))
        lengths = [len(json.dumps(item, ensure_ascii=False)) for item in forward]
        return {
            **base,
            "forward": first,
            "reverse": second,
            "consensus": agreed,
            "shadow_top_id": agreed["winner_id"],
            "swap_consistent": agreed["swap_consistent"],
            "length_correlation": _pearson(lengths, ranks),
            "status": "completed",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:  # best-effort shadow must never break planning
        return {
            **base,
            "forward": {},
            "reverse": {},
            "consensus": {"winner_id": None, "status": "tie",
                          "swap_consistent": False},
            "shadow_top_id": None,
            "swap_consistent": False,
            "length_correlation": None,
            "status": "unavailable",
            "note": str(exc)[:200],
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
