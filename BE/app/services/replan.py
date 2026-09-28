"""Rolling-horizon replan + mode gate + version++ (T046, lane B).

replan(state, event, pois, travel, trip): event is a DynamicEvent dict
passed DIRECTLY (STUB-NOTE: lane-A event_clf T044 classifies text into
events at phase-PR). Completed activities are fixed (T045 contract);
only remaining is re-optimized (T017), then validated (T018).

Modes: plan (new version), clarify (event conflicts a hard constraint
-> ask priority, state untouched), no_solution (structured, completed
still preserved).
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.services import state as store  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.app.services.validator import validate  # noqa: E402


def _mm(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


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
           travel: dict[tuple[str, str], int], trip: dict) -> dict:
    """Return {"itinerary" (versioned) | None, "mode", "changes", ...}."""
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
            travel2.setdefault(("depot", x),
                               travel.get((last, x), travel.get((x, last), 0)))

    stub = [StubPOI(pid, int(by_id[pid].get("visit_min", 60)),
                    *_win(by_id[pid], trip, state), 1.0)
            for pid in cand_ids if pid in by_id]
    start = max(_mm(state.get("now", trip.get("start_time", "07:00"))),
                _mm(trip.get("start_time", "07:00")))
    out = optimize(stub, travel2, StubTrip(start, _mm(trip.get("end_time", "18:00"))))
    if out["itinerary"] is None and cand_ids:
        return {"itinerary": None, "mode": "no_solution",
                "reason": out.get("reason", "vo nghiem"),
                "preserved_completed": completed_ids,
                "changes": [], "version": state["version"]}
    acts = out["itinerary"]["activities"] if out["itinerary"] else []
    if not acts and cand_ids:
        return {"itinerary": None, "mode": "no_solution",
                "reason": "khong xep duoc remaining nao",
                "preserved_completed": completed_ids,
                "changes": [], "version": state["version"]}
    matrix = {f"{a}->{b}": {"minutes": w} for (a, b), w in travel.items()}
    rep = validate({"activities": acts}, trip,
                   {p["poi_id"]: {"verified": True, "fee": p.get("fee", 0),
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
    hours = p.get("opening_hours", [])
    if hours:
        o, c = hours[0].split("-")
        return _mm(o), _mm(c)
    return _mm(state.get("now", trip.get("start_time", "07:00"))), \
        _mm(trip.get("end_time", "18:00"))
