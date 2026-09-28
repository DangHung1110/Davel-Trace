"""Trip state store + delta + preservation contract (T045, lane B).

State: {trip_id, version, now, location, completed[], cancelled[],
remaining[], history[]}. FR-047: every preference change records a
state_delta AND bumps version. Preservation contract: completed items
are IMMUTABLE — apply_delta may only touch remaining; attempts to
drop/alter completed are ignored and noted.

STUB-NOTE (as T017/T018): plain-dict activities; in-memory store
(STUB: persistent store wires at phase-PR with T046). Real plan
schemas (T007) swap in without changing this logic.
"""

from __future__ import annotations

import copy
import time

_STORE: dict[str, dict] = {}


def new_state(trip_id: str, activities: list[dict],
              start_time: str = "07:00",
              location: str = "") -> dict:
    state = {"trip_id": trip_id, "version": 1, "now": start_time,
             "location": location, "completed": [], "cancelled": [],
             "remaining": [dict(a, status="planned") for a in activities],
             "history": []}
    _STORE[trip_id] = state
    return copy.deepcopy(state)


def load(trip_id: str) -> dict:
    if trip_id not in _STORE:
        raise KeyError(f"no state for trip {trip_id}")
    return copy.deepcopy(_STORE[trip_id])


def complete(state: dict, poi_id: str, at: str = "") -> dict:
    """Move a remaining activity to completed (progress, no version bump)."""
    state = copy.deepcopy(state)
    for i, a in enumerate(state["remaining"]):
        if a["poi_id"] == poi_id:
            done_at = at or time.strftime("%H:%M")
            done = dict(state["remaining"].pop(i), status="done", done_at=done_at)
            state["completed"].append(done)
            state["now"] = done_at  # rolling horizon advances with progress
            _STORE[state["trip_id"]] = state
            return copy.deepcopy(state)
    raise KeyError(f"{poi_id} not in remaining")


def apply_delta(state: dict, delta: dict) -> dict:
    """Apply {add[], drop[], preferences, now, location} -> version++.

    Completed items are never modified or removed; violations are noted
    in the recorded delta entry. Copy-on-write: the input is untouched.
    """
    state = copy.deepcopy(state)
    completed_ids = {a["poi_id"] for a in state["completed"]}
    ignored = [pid for pid in delta.get("drop", []) if pid in completed_ids]
    kept = [a for a in state["remaining"] if a["poi_id"] not in delta.get("drop", [])
            or a["poi_id"] in completed_ids]
    dropped = [a["poi_id"] for a in state["remaining"]
               if a["poi_id"] in delta.get("drop", []) and a["poi_id"] not in completed_ids]
    for a in state["remaining"]:
        if a["poi_id"] in dropped:
            state["cancelled"].append(dict(a, status="cancelled"))
    state["remaining"] = kept + [dict(a, status="planned") for a in delta.get("add", [])]
    if delta.get("now"):
        state["now"] = delta["now"]
    if delta.get("location"):
        state["location"] = delta["location"]
    state["version"] += 1
    state["history"].append({"version": state["version"],
                             "delta": {"add": [a.get("poi_id") for a in delta.get("add", [])],
                                       "drop": list(delta.get("drop", [])),
                                       "preferences": delta.get("preferences", {}),
                                       "ignored_completed": ignored}})
    _STORE[state["trip_id"]] = state
    return copy.deepcopy(state)
