"""Rolling-horizon replan + mode gate + version++ (T046, lane B).

replan(state, event, pois, travel, trip): event is a DynamicEvent dict
passed DIRECTLY (STUB-NOTE: lane-A event_clf T044 classifies text into
events at phase-PR). Completed activities are fixed (T045 contract);
only remaining is re-optimized (T017), then validated (T018).

Horizon is the ETB hard deadline `_deadline(trip)` = min(end_time,
return_time): a `return_time` is a hard within-day cap and is NEVER
silently stretched to end_time (T046). Used for the optimizer's Tmax
and the opening-hours fallback window.

Modes: plan (new version), clarify (event conflicts a hard constraint
-> ask priority, state untouched), no_solution (structured, completed
still preserved).
"""

from __future__ import annotations

from BE.app.services import scorer
from BE.app.services import state as store
from BE.app.services.budget import tighten_budget
from BE.app.services.common import party_size, to_min
from BE.app.services.optimizer import (
    StubPOI, StubTrip, optimize, poi_visit_min)
from BE.app.services.soft_rules import CATEGORY_DAILY_CAP, cafe_cap
from BE.app.services.validator import validate
from BE.common import effective_fee, poi_open_windows


def _deadline(trip: dict) -> int:
    """ETB hard within-day deadline: min(end_time, return_time) (T046).

    `return_time` (when set) is a hard cap — the horizon is never
    silently stretched to `end_time`. Defaults to end_time "18:00".
    """
    end = to_min(trip.get("end_time", "18:00"))
    rt = trip.get("return_time")
    return min(end, to_min(rt)) if rt else end


def _event_drops(event: dict, remaining: list[dict], by_id: dict) -> set[str]:
    etype = event.get("type", "")
    drops: set[str] = set()
    if etype in ("rain",):
        drops = {a["poi_id"] for a in remaining
                 if (by_id.get(a["poi_id"], {}) or {}).get("weather_sensitive")}
    elif etype == "drop_poi":
        drops = set(event.get("affected", []))
    elif etype == "tired":
        drops = {a["poi_id"] for a in remaining
                 if int((by_id.get(a["poi_id"], {}) or {}).get("intensity", 2)) >= 3}
    elif etype == "closure":
        drops = set(event.get("affected", []))
    drops |= set(event.get("delta", {}).get("drop", []))
    return drops


def replan(state: dict, event: dict, pois: list[dict],
           travel: dict[tuple[str, str], int], trip: dict,
           budget_state: dict | None = None) -> dict:
    """Return {"itinerary" (versioned) | None, "mode", "changes", ...}.

    `budget_state` is the lane-C raw `replan_budget()` snapshot
    {trip_id, budget, spent, left, by_kind, alert}; when supplied, the
    validator gates new activities against `allowed_remaining` (actual
    funds left), not the trip's original total. `trip`/`budget_state`
    are never mutated. Omitted -> legacy behavior (trip budget).
    """
    by_id = {p["poi_id"]: p for p in pois}
    completed_ids = [a["poi_id"] for a in state.get("completed", [])]
    remaining = list(state.get("remaining", []))

    # clarify: event demands must_keep that violates a hard constraint
    must_keep = set(event.get("delta", {}).get("must_keep", []))
    avoid = set(trip.get("avoid", []))
    clash = sorted(must_keep & avoid)
    if clash:
        return {"itinerary": None, "mode": "clarify",
                "question": f"must_keep xung dot avoid: {clash} — uu tien ben nao?",
                "changes": [], "version": state["version"]}

    drops = _event_drops(event, remaining, by_id) - set(completed_ids)
    added = list(event.get("delta", {}).get("add", []))
    cand_ids = [a["poi_id"] for a in remaining if a["poi_id"] not in drops]
    cand_ids += [a["poi_id"] if isinstance(a, dict) else a for a in added
                 if (a["poi_id"] if isinstance(a, dict) else a) not in cand_ids]

    # depot legs from the last completed POI (rolling horizon continuity)
    travel2 = dict(travel)
    if completed_ids:
        last = completed_ids[-1]
        for x in cand_ids:
            leg = travel.get((last, x))
            if leg is None:
                travel2.pop(("depot", x), None)
            else:
                travel2[("depot", x)] = leg

    stub = [StubPOI(pid, poi_visit_min(by_id[pid]),
                    *_win(by_id[pid], trip, state), 1.0,
                    fee=effective_fee(by_id[pid]) or 0)
            for pid in cand_ids if pid in by_id]
    effective_trip = trip
    if budget_state is not None:
        tight = tighten_budget(budget_state, trip)
        effective_trip = dict(trip, budget=tight["allowed_remaining"])
    max_fee = (None if effective_trip.get("budget") is None
               else int(effective_trip["budget"]) // party_size(trip))
    start = max(to_min(state.get("now", trip.get("start_time", "07:00"))),
                to_min(trip.get("start_time", "07:00")))
    # T061a: no completed -> open tour (origin_id None) when the plan has no
    # depot cell; with completed the rolling horizon anchors on the last one.
    origin_id = "depot" if completed_ids else (trip.get("origin_id") or None)
    q = scorer.edge_scores([pid for pid in cand_ids if pid in by_id], by_id)
    out = optimize(stub, travel2, StubTrip(start, _deadline(trip), origin_id),
                   edge_scores=q,
                   # Universal HARD caps the gate checks: a replanned day must
                   # not end up with two markets / two cafes just because the
                   # rolling horizon re-optimised from scratch.
                   category_cap=CATEGORY_DAILY_CAP,
                   cafe_cap=None if not trip.get("profile")
                   else cafe_cap(trip.get("profile")),
                   max_fee=max_fee)
    if out["itinerary"] is None and cand_ids:
        return {"itinerary": None, "mode": "no_solution",
                "reason": out.get("reason", "vo nghiem"),
                "preserved_completed": completed_ids,
                "changes": [], "version": state["version"]}
    acts = out["itinerary"]["activities"] if out["itinerary"] else []
    if not acts and cand_ids:
        over_budget = max_fee is not None and any(s.fee > max_fee for s in stub)
        return {"itinerary": None, "mode": "no_solution",
                "reason": ("khong xep duoc remaining nao trong ngan sach con lai (BCS)"
                           if over_budget else "khong xep duoc remaining nao"),
                "preserved_completed": completed_ids,
                "changes": [], "version": state["version"]}
    matrix = {f"{a}->{b}": {"minutes": w} for (a, b), w in travel.items()}
    # A must_visit already done is not in the remaining plan; HCS would otherwise
    # fail every replan after it.
    open_must = [m for m in effective_trip.get("must_visit", []) if m not in completed_ids]
    rep = validate({"activities": acts}, {**effective_trip, "must_visit": open_must},
                   {p["poi_id"]: {"verified": p.get("verified", False),
                                  "fee": effective_fee(p) or 0,
                                  "opening_hours": p.get("opening_hours", [])}
                    for p in pois}, matrix)
    if acts and not rep["passed"]:
        return {"itinerary": None, "mode": "no_solution",
                "reason": f"rot cong {rep['violations']}",
                "preserved_completed": completed_ids,
                "changes": [], "version": state["version"]}

    changes = [{"action": "keep", "poi_id": pid} for pid in completed_ids]
    changes += [{"action": "drop", "poi_id": pid,
                 "reason": event.get("type", "event")} for pid in sorted(drops)]
    new_ids = [a["poi_id"] for a in acts]
    changes += [{"action": "add", "poi_id": pid} for pid in new_ids
                if pid not in [a["poi_id"] for a in remaining]]
    new_state = store.apply_delta(dict(state), {"drop": sorted(drops),
                                                "add": [{"poi_id": a["poi_id"],
                                                         "start": a["start"],
                                                         "end": a["end"]} for a in acts],
                                                "preferences": event.get("delta", {})})
    return {"itinerary": {"activities": acts, "version": new_state["version"]},
            "mode": "plan", "changes": changes, "version": new_state["version"],
            "preserved_completed": completed_ids}


def _win(p: dict, trip: dict, state: dict) -> tuple[int, int]:
    wins = poi_open_windows(p)  # real hours, else the category's safe hours
    if wins is not None:
        return wins[0] if wins else (0, 0)
    return (to_min(state.get("now", trip.get("start_time", "07:00"))),
            _deadline(trip))  # fallback window also clamps to the deadline
