"""Trips of several days (FR-020): one solve per day, merged into one plan.

Days are solved in order because each one depends on the last: no POI twice, a
budget shared by the whole trip, and a wish met once needs no repeat. Solving
them as one model would multiply the nodes, and CP-SAT already needs the 80
candidate cap for a single day.

- Budget: each day may spend its share of what is left, so an early day cannot
  eat the whole trip. A day that cannot be planned on its share retries with all
  that is left (a dear must_visit).
- must_visit: spread evenly over the days, because a day holds one POI per
  category; if that fails, all on the first day.
- Activities: a day only has to meet the wishes the days before it did not.

A one-day trip goes straight to the solver and its plan is untouched. A longer
one is one plan: `activities` and `segments` carry `day`, `days` holds the summary
per day, and the totals and gate verdict cover the whole trip.
"""

from __future__ import annotations

import datetime

from BE.app.services import profiles
from BE.common import effective_fee, party_size

DAY_FIELDS = ("total_cost", "total_km", "total_min", "travel_min")


def day_date(date: str, offset: int) -> str:
    """ISO date `offset` days later; "" when the trip has no usable date."""
    try:
        start = datetime.date.fromisoformat(date or "")
    except ValueError:
        return ""
    return (start + datetime.timedelta(days=offset)).isoformat()


def _usable(plan: dict) -> bool:
    return bool(plan.get("activities")) and bool(plan.get("passed"))


def _open_wishes(wishes: list[str], plan: dict) -> list[str]:
    met = {m.get("activity") for m in plan.get("activity_match") or []
           if m.get("status") == "met"}
    return [wish for wish in wishes if wish not in met]


def _solve_days(solve, trip: dict, days: int, pack_first: bool) -> list[dict]:
    """Day by day until the trip is planned or a day cannot be."""
    remaining = None if trip.get("budget") is None else int(trip["budget"])
    must = list(trip.get("must_visit") or [])
    wishes = list(trip.get("activities") or [])
    used: set[str] = set()
    plans = []
    for index in range(days):
        left = days - index
        today = must if pack_first or left == 1 else must[::left]
        budgets = ([None] if remaining is None
                   else [remaining // left, remaining] if left > 1 else [remaining])
        for budget in budgets:
            day_trip = {**trip, "days": 1, "date": day_date(trip.get("date"), index),
                        "must_visit": today, "activities": wishes}
            if budget is not None:
                day_trip["budget"] = budget
            # Only the last attempt explains itself: the diagnosis costs extra solves.
            plan = solve(day_trip, frozenset(used), budget == budgets[-1])
            if _usable(plan):
                break
        plans.append(plan)
        if not _usable(plan):
            break
        ids = {a["poi_id"] for a in plan["activities"]}
        used |= ids
        must = [m for m in must if m not in ids]
        wishes = _open_wishes(wishes, plan)
        if remaining is not None:
            remaining -= int(plan.get("total_cost") or 0)
    return plans


def _merge_matches(plans: list[dict]) -> list[dict]:
    """One entry per wish: met if any day met it, else what the first day said."""
    merged: dict[str, dict] = {}
    for plan in plans:
        for entry in plan.get("activity_match") or []:
            key = entry.get("activity")
            if key not in merged or entry.get("status") == "met":
                merged[key] = entry
    return list(merged.values())


def _merge_warnings(plans: list[dict], match: list[dict]) -> list[str]:
    """Warnings that repeat on every day stay as they are; the rest name their day."""
    day_lines = []
    for plan in plans:
        own = set(profiles._activity_warnings(plan.get("activity_match") or []))
        day_lines.append([w for w in plan.get("warnings") or [] if w not in own])
    out: list[str] = []
    for number, lines in enumerate(day_lines, start=1):
        for line in lines:
            text = (line if all(line in other for other in day_lines)
                    else f"ngay {number}: {line}")
            if text not in out:
                out.append(text)
    return out + [w for w in profiles._activity_warnings(match) if w not in out]


def _diversity(plans: list[dict]) -> dict:
    reports = [p.get("diversity") or {} for p in plans]
    stops = [len(p.get("activities") or []) for p in plans]
    categories = sorted({c for r in reports for c in r.get("categories") or []})
    return {**reports[0], "categories": categories, "distinct_categories": len(categories),
            "novel_stops": sum(r.get("novel_stops") or 0 for r in reports),
            "novelty": round(sum((r.get("novelty") or 0.0) * n for r, n in zip(reports, stops))
                             / max(1, sum(stops)), 4)}


def merge_days(plans: list[dict], trip: dict, days: int, check) -> dict:
    """Day plans -> one plan. `check(itinerary, trip)` is the gate over the whole trip."""
    acts, segments, summary = [], [], []
    for number, plan in enumerate(plans, start=1):
        acts += [{**a, "day": number} for a in plan.get("activities") or []]
        segments += [{**s, "day": number} for s in plan.get("segments") or []]
        summary.append({
            "day": number, "date": day_date(trip.get("date"), number - 1),
            "stops": len(plan.get("activities") or []),
            **{field: plan.get(field) for field in DAY_FIELDS},
            "cost_estimated": bool(plan.get("cost_estimated")),
            "passed": bool(plan.get("passed")),
            "violations": plan.get("violations") or [],
            "template": plan.get("template"),
            "soft_penalties": plan.get("soft_penalties"),
        })
    stops = [len(p.get("activities") or []) for p in plans]
    match = _merge_matches(plans)
    merged = {**plans[0], "activities": acts, "segments": segments, "days": summary,
              "cost_estimated": any(p.get("cost_estimated") for p in plans),
              "preference": round(sum(float(p.get("preference") or 0.0) * n
                                      for p, n in zip(plans, stops)) / max(1, sum(stops)), 3),
              "diversity": _diversity(plans),
              "activity_match": match}
    for field in DAY_FIELDS:
        merged[field] = sum(p.get(field) or 0 for p in plans)
    merged["total_km"] = round(merged["total_km"], 2)
    merged["soft_penalties"] = {
        "penalty": round(sum((p.get("soft_penalties") or {}).get("penalty") or 0.0 for p in plans), 4),
        "issues": [issue for p in plans for issue in (p.get("soft_penalties") or {}).get("issues") or []]}

    report = check({"activities": acts, "total_cost": merged["total_cost"]}, trip)
    complete = len(plans) == days and all(stops)
    merged["passed"] = bool(report["passed"]) and complete
    merged["violations"] = list(report["failed"])
    merged["soft_violations"] = list(report["soft_failed"])
    merged["constraint_status"] = {name: int(ok) for name, ok in report["checks"].items()
                                   if name in plans[0].get("constraint_status", {})}
    # Route efficiency is a per-day idea: a second day must not count as a detour.
    merged["scores"] = profiles.score_plan({**merged, "travel_min": merged["travel_min"] / days})
    warnings = _merge_warnings(plans, match)
    if not complete:
        warnings.append(f"chi xep duoc {sum(1 for n in stops if n)}/{days} ngay")
    if warnings:
        merged["warnings"] = warnings
    else:
        merged.pop("warnings", None)
    for plan in plans:
        if plan.get("infeasible_by"):
            merged["infeasible_by"] = plan["infeasible_by"]
            break
    rungs = [p.get("_rung") for p in plans]
    if None in rungs:
        merged.pop("_rung", None)
    else:
        merged["_rung"] = max(rungs)
    candidates = {poi["poi_id"]: poi for p in plans
                  for poi in (p.get("_context") or {}).get("pois") or []}
    travel: dict = {}
    for plan in plans:
        travel.update((plan.get("_context") or {}).get("travel") or {})
    merged["_context"] = {"trip": trip, "pois": list(candidates.values()), "travel": travel}
    return merged


def build_trip(solve, trip: dict, check) -> dict:
    """`solve(day_trip, used_ids, diagnose)` plans one day; a one-day trip is just that.

    Spreading must_visit may fail where packing them works (and the reverse), so
    a failed spread gets one more try; the first attempt's plans are reported if
    neither works.
    """
    days = int(trip.get("days") or 1)
    if days <= 1:
        return solve(trip, frozenset(), True)
    attempts = [False, True] if len(trip.get("must_visit") or []) > 1 else [False]
    first = None
    for pack_first in attempts:
        plans = _solve_days(solve, trip, days, pack_first)
        merged = merge_days(plans, trip, days, check)
        if merged["passed"]:
            return merged
        first = first or merged
    return first


def active_day(acts: list[dict], done: set[str]) -> int:
    """The first day with a stop still to do (the last day when all are done)."""
    days = sorted({a["day"] for a in acts})
    return next((d for d in days
                 if any(a["day"] == d and a["poi_id"] not in done for a in acts)), days[-1])


def day_scope(trip: dict, others: list[dict], today: list[dict], pois: dict) -> dict:
    """The trip one day of a replan works on: what the other days cost is gone
    from the budget, and only this day's must_visit bind."""
    scope = {**trip, "days": 1}
    if trip.get("budget") is not None:
        spent = sum(effective_fee(pois.get(a["poi_id"]) or {}) or 0 for a in others)
        scope["budget"] = max(0, int(trip["budget"]) - spent * party_size(trip))
    ids = {a["poi_id"] for a in today}
    scope["must_visit"] = [m for m in trip.get("must_visit") or [] if m in ids]
    return scope
