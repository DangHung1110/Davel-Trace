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
from BE.app.services.common import hh, party_size, to_min, total_fee
from BE.app.services.gate import check_profile_safe
from BE.app.services.optimizer import (
    StubPOI, StubTrip, optimize, poi_visit_min)
from BE.app.services.profiles import _gate_view
from BE.app.services.soft_rules import (
    CATEGORY_DAILY_CAP, MEAL_SLOTS, cafe_cap, clip_to_time_fit, lunch_activity, poi_category,
    rest_span, time_fit_windows)
from BE.app.services.templates import universal_constraints
from BE.app.services.validator import validate
from BE.common import effective_fee, poi_open_windows, trusted_rating


# Lunch has to start by then (gate REST_FOLLOWS_LUNCH).
LUNCH_LATEST_MIN = 13 * 60
LUNCH_SUBSTITUTES = 5
# One worker on a budget of work, like /v1/itinerary: the same incident on the same
# plan gets the same answer, and these small solves finish far inside the budget.
REPLAN_WORKERS = 1
REPLAN_DETERMINISTIC_TIME = 2.0


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
    # Rain or tiredness never cancels what the traveler insisted on; only an
    # explicit drop or a closure can.
    held_must = set()
    if event.get("type") in ("rain", "tired"):
        held_must = drops & set(trip.get("must_visit", []))
        drops -= held_must
    added = list(event.get("delta", {}).get("add", []))
    cand_ids = [a["poi_id"] for a in remaining if a["poi_id"] not in drops]
    cand_ids += [a["poi_id"] if isinstance(a, dict) else a for a in added
                 if (a["poi_id"] if isinstance(a, dict) else a) not in cand_ids]

    # The gate judges the whole day, what is done included: lunch and the caps may
    # already be behind us. What is done is paid, so only the rest is budgeted.
    done = list(state.get("completed", []))
    party = party_size(trip)
    done_cost = total_fee(done, by_id, party)
    allowed = None if trip.get("budget") is None else max(0, int(trip["budget"]) - done_cost)
    if budget_state is not None:
        allowed = tighten_budget(budget_state, trip)["allowed_remaining"]
    max_fee = None if allowed is None else allowed // party
    gate_trip = trip if allowed is None else dict(trip, budget=allowed + done_cost)
    start = max(to_min(state.get("now", trip.get("start_time", "07:00"))),
                to_min(trip.get("start_time", "07:00")))
    # Lunch: still to come (the solver places it and keeps the rest after it), done
    # (keep the rest clear), or missed: a delay past the window must not make the
    # day unplannable, so the day rules that need a lunch are dropped.
    limits = universal_constraints(trip)
    lunch_done = lunch_activity(sorted(done, key=lambda a: a["start"]), by_id) is not None
    lunch_missed = bool(limits["lunch_required"]) and not lunch_done and start >= LUNCH_LATEST_MIN
    plan_lunch = bool(limits["lunch_required"]) and not lunch_done and not lunch_missed
    blocked = None
    if lunch_done and limits["rest_after_lunch"]:
        span = rest_span(done, by_id, trip["profile"], _deadline(trip))
        blocked = (span["start"], span["end"]) if span else None
    if lunch_missed:
        gate_trip = {k: v for k, v in gate_trip.items() if k != "profile"}

    # The event took the only restaurant (an open-air lunch in the rain): a day
    # still needs a lunch, so offer the best dry ones, else keep the dropped one.
    substitutes: list[str] = []
    if plan_lunch and not any(poi_category(by_id.get(pid)) == "restaurant" for pid in cand_ids):
        taken = {*cand_ids, *completed_ids, *drops}
        dry = sorted((p for p in pois
                      if p["poi_id"] not in taken and p.get("verified")
                      and poi_category(p) == "restaurant" and not p.get("weather_sensitive")
                      and (max_fee is None or (effective_fee(p) or 0) <= max_fee)),
                     key=lambda p: -trusted_rating(p))
        substitutes = [p["poi_id"] for p in dry[:LUNCH_SUBSTITUTES]]
        if not substitutes:
            held = {pid for pid in drops if poi_category(by_id.get(pid)) == "restaurant"}
            drops -= held
            cand_ids += sorted(held)
        cand_ids += substitutes

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

    named = set(trip.get("must_visit", []))
    stub = [_stub(by_id[pid], trip, state,
                  trusted_rating(by_id[pid]) / 5 if pid in substitutes else 1.0,
                  named=pid in named, lunch_done=lunch_done)
            for pid in cand_ids if pid in by_id]
    # T061a: no completed -> open tour (origin_id None) when the plan has no
    # depot cell; with completed the rolling horizon anchors on the last one.
    origin_id = "depot" if completed_ids else (trip.get("origin_id") or None)
    q = scorer.edge_scores([pid for pid in cand_ids if pid in by_id], by_id)
    # The gate reads the whole day: what comes next must not repeat what was just done.
    last_done = max(done, key=lambda a: a["start"]) if done else None
    last_cat = poi_category(by_id.get(last_done["poi_id"])) if last_done else ""
    not_first = {pid for pid in cand_ids if pid in by_id and last_cat
                 and poi_category(by_id[pid]) == last_cat}
    out = optimize(stub, travel2, StubTrip(start, _deadline(trip), origin_id),
                   edge_scores=q, workers=REPLAN_WORKERS,
                   deterministic_time=REPLAN_DETERMINISTIC_TIME, not_first=not_first,
                   # Universal HARD caps the gate checks: a replanned day must
                   # not end up with two markets / two cafes just because the
                   # rolling horizon re-optimised from scratch.
                   category_cap=CATEGORY_DAILY_CAP,
                   cafe_cap=None if not trip.get("profile")
                   else cafe_cap(trip.get("profile")),
                   no_consecutive=True, no_adjacent_food=True,
                   must_visit=[m for m in trip.get("must_visit", []) if m in cand_ids],
                   lunch_required=plan_lunch,
                   rest_after_lunch=limits["rest_minutes"] if plan_lunch else None,
                   blocked_window=blocked,
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
    pois_gate = {p["poi_id"]: _gate_view(p) for p in pois}
    # What is done is a fact: only the day rules read it, not its hours or its legs.
    done_ids = [a["poi_id"] for a in done]
    for pid in done_ids:
        if pid in pois_gate:
            pois_gate[pid] = {**pois_gate[pid], "opening_hours": ["00:00-23:59"]}
    matrix.update({f"{a}->{b}": {"minutes": 0} for a in done_ids for b in done_ids if a != b})
    whole_day = {"activities": [*done, *acts]}
    rep = validate(whole_day, gate_trip, pois_gate, matrix)
    violations = list(rep["violations"])
    if lunch_missed and not check_profile_safe(whole_day, trip, pois_gate, matrix)["passed"]:
        violations.append("PROFILE_SAFE")
    if acts and violations:
        return {"itinerary": None, "mode": "no_solution",
                "reason": f"rot cong {violations}",
                "preserved_completed": completed_ids,
                "changes": [], "version": state["version"]}

    changes = [{"action": "keep", "poi_id": pid} for pid in completed_ids]
    changes += [{"action": "keep", "poi_id": pid, "reason": "diem bat buoc"}
                for pid in sorted(held_must)]
    changes += [{"action": "drop", "poi_id": pid,
                 "reason": event.get("type", "event")} for pid in sorted(drops)]
    new_ids = [a["poi_id"] for a in acts]
    changes += [{"action": "add", "poi_id": pid,
                 "reason": "thay nha hang bi bo" if pid in substitutes else "theo yeu cau"}
                for pid in new_ids if pid not in [a["poi_id"] for a in remaining]]
    new_state = store.apply_delta(dict(state), {"drop": sorted(drops),
                                                "add": [{"poi_id": a["poi_id"],
                                                         "start": a["start"],
                                                         "end": a["end"]} for a in acts],
                                                "preferences": event.get("delta", {})})
    return {"itinerary": {"activities": acts, "version": new_state["version"]},
            "mode": "plan", "changes": changes, "version": new_state["version"],
            "preserved_completed": completed_ids}


def _stub(p: dict, trip: dict, state: dict, score: float, named: bool = False,
          lunch_done: bool = False) -> StubPOI:
    """A stop keeps the hours it makes sense at, as the plan did, unless the traveller
    named it. With lunch behind us a restaurant left in the day is dinner: moved up
    next to lunch it would fail the gate and cost the whole replan."""
    wins = poi_open_windows(p)  # real hours, else the category's safe hours
    category = poi_category(p)
    if wins and not named:
        wins = clip_to_time_fit(p, wins)
    if wins and lunch_done and category == "restaurant":
        floor = MEAL_SLOTS[1][0] if time_fit_windows(p) else MEAL_SLOTS[0][1]
        wins = [(max(lo, floor), hi) for lo, hi in wins if hi > floor]
    if wins is None:  # the fallback window also clamps to the deadline
        span = (to_min(state.get("now", trip.get("start_time", "07:00"))), _deadline(trip))
    else:
        span = (wins[0][0], wins[-1][1]) if wins else (0, 0)
    return StubPOI(p["poi_id"], poi_visit_min(p), *span, score,
                   restaurant=category == "restaurant", category=category,
                   fee=effective_fee(p) or 0,
                   windows=tuple(wins) if wins and len(wins) > 1 else ())
