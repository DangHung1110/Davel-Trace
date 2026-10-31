"""Best order and clock times for the stops the solver chose.

The solver decides WHAT a day holds. Stopped at its budget it rarely leaves the
shortest ORDER of those stops (the audit found routes 1.41 times the shortest, one
in three over 1.5 times), and its clock times are whatever satisfied the model, so
a stop can wait an hour in front of a lunch nobody was late for.

This pass takes the chosen stops and searches their orders exactly, keeping every
rule of the day: opening windows, the lunch and dinner each restaurant was chosen
for, the rest after lunch, the cafe dayparts, no two neighbours of one category, the
order the traveller asked for. Free time then goes into longer stays, and what is
left collects at the start of the day or after the rest, in the heat of the day, not
as holes between stops. The caller re-checks the result with the gate; any doubt
keeps the solver's plan.
"""

from __future__ import annotations

from dataclasses import replace

from BE.app.services.common import hh, to_min
from BE.app.services.soft_rules import (
    CAFE_AFTERNOON_START,
    CAFE_MORNING_END,
    DINNER_REQUIRED,
    LUNCH_REQUIRED,
    MEAL_SLOTS,
)

# Order search budget in visited nodes. Nine stops are searched exhaustively once
# the windows prune them; a count, not a clock, so the same plan comes back.
MAX_NODES = 150_000


def _meal_slot(minutes: int) -> int | None:
    for index, (lo, hi) in enumerate(MEAL_SLOTS):
        if lo <= minutes < hi:
            return index
    return None


def _role(stub, start: int, cafes: int) -> str | None:
    """What this stop was chosen for, read off the solver's own clock time."""
    if stub.restaurant:
        if LUNCH_REQUIRED[0] <= start < LUNCH_REQUIRED[1]:
            return "lunch"
        if DINNER_REQUIRED[0] <= start < DINNER_REQUIRED[1]:
            return "dinner"
    if stub.category == "cafe" and cafes == 2:
        return "cafe_morning" if start < CAFE_MORNING_END else "cafe_afternoon"
    return None


def _earliest(role: str | None, clock: int) -> int | None:
    """Earliest allowed start for a role, None when the clock is already past it."""
    if role == "lunch":
        return max(clock, LUNCH_REQUIRED[0]) if clock < LUNCH_REQUIRED[1] else None
    if role == "dinner":
        return max(clock, DINNER_REQUIRED[0]) if clock < DINNER_REQUIRED[1] else None
    if role == "cafe_morning":
        return clock if clock < CAFE_MORNING_END else None
    if role == "cafe_afternoon":
        return max(clock, CAFE_AFTERNOON_START + 1)
    return clock


def _place(stub, earliest: int, end_min: int) -> tuple[int, int] | None:
    """(start, close of the window it sits in): earliest window that holds the visit."""
    for lo, hi in (stub.windows or ((stub.open_min, stub.close_min),)):
        close = min(hi, end_min)
        start = max(earliest, lo)
        if start + stub.visit_min <= close:
            return start, close
    return None


def _last_start(role: str | None, close: int, visit: int) -> int:
    """Latest allowed start: its window, and the role's own limit."""
    last = close - visit
    if role == "lunch":
        last = min(last, LUNCH_REQUIRED[1] - 1)
    elif role == "dinner":
        last = min(last, DINNER_REQUIRED[1] - 1)
    elif role == "cafe_morning":
        last = min(last, CAFE_MORNING_END - 1)
    return last


def held_to(stub, span: list[int]):
    """The stub with its windows cut so a visit can only START inside `span`."""
    windows = stub.windows or ((stub.open_min, stub.close_min),)
    return replace(stub, windows=tuple(
        (max(lo, span[0]), min(hi, span[1] + stub.visit_min))
        for lo, hi in windows if max(lo, span[0]) < min(hi, span[1] + stub.visit_min)))


def best_order(acts: list[dict], stubs: dict, travel: dict, start_min: int, end_min: int,
               overhead: int, rest_minutes: int | None = None, late_end_min: int | None = None,
               precedence: list | None = None, no_consecutive: bool = True,
               fixed_first: str | None = None) -> list[dict] | None:
    """The stops in their shortest legal order with new clock times, None when the
    search cannot even rebuild the solver's own day (the caller keeps that one)."""
    ids = [a["poi_id"] for a in acts]
    if len(ids) < 2 or any(pid not in stubs for pid in ids):
        return None
    cafes = sum(1 for pid in ids if stubs[pid].category == "cafe")
    roles = {a["poi_id"]: _role(stubs[a["poi_id"]], to_min(a["start"]), cafes) for a in acts}
    before = {pid: {x for x, y in precedence or [] if y == pid and x in ids} for pid in ids}

    best: dict = {"travel": None, "order": None}
    nodes = 0

    def walk(order: list, clock: int, used: frozenset, spent: int, rest_until: int,
             slots: frozenset) -> None:
        nonlocal nodes
        if nodes >= MAX_NODES:
            return
        if best["travel"] is not None and spent >= best["travel"]:
            return
        if len(order) == len(ids):
            last_end = order[-1][1] + stubs[order[-1][0]].visit_min
            if late_end_min is None or last_end >= late_end_min:
                best["travel"], best["order"] = spent, list(order)
            return
        prev = order[-1][0] if order else None
        for pid in ids:
            if pid in used or not before[pid] <= used:
                continue
            if not order and fixed_first and pid != fixed_first:
                continue
            nodes += 1
            stub = stubs[pid]
            leg = 0
            if prev is not None:
                if no_consecutive and stub.category and stub.category == stubs[prev].category:
                    continue
                if stub.restaurant and stubs[prev].restaurant:
                    continue
                need = travel.get((prev, pid))
                if need is None:
                    continue
                leg = need
            earliest = _earliest(roles[pid], max(clock + leg + (overhead if prev else 0), rest_until))
            if earliest is None:
                continue
            placed = _place(stub, earliest, end_min)
            if placed is None or (roles[pid] and placed[0] > _last_start(roles[pid], placed[1], stub.visit_min)):
                continue
            start = placed[0]
            slot = _meal_slot(start) if stub.restaurant else None
            if slot is not None and slot in slots:
                continue
            finish = start + stub.visit_min
            walk(order + [(pid, start, placed[1])], finish, used | {pid}, spent + leg,
                 finish + rest_minutes if (roles[pid] == "lunch" and rest_minutes) else rest_until,
                 slots | {slot} if slot is not None else slots)

    walk([], start_min, frozenset(), 0, 0, frozenset())
    if best["order"] is None:
        return None
    return _close_gaps(best["order"], stubs, roles, travel, overhead, rest_minutes)


def _close_gaps(order: list, stubs: dict, roles: dict, travel: dict, overhead: int,
                rest_minutes: int | None) -> list[dict]:
    """Honest clock times for a fixed order.

    The stops leading up to a meal first spend the free time on longer stays, up to
    the usual longest (p75). What is left moves to the front of that run: the day
    starts a little later, or the rest after lunch runs longer, instead of a hole in
    front of dinner. After the last meal stops keep their earliest times and may only
    stretch into a gap. Lunch with a rest stays as it is: the rest starts at its end.
    """
    earliest = [start for _pid, start, _close in order]
    starts = list(earliest)
    visits = [stubs[pid].visit_min for pid, _start, _close in order]
    legs = [travel.get((order[i][0], order[i + 1][0]), 0) + overhead for i in range(len(order) - 1)]

    def latest_starts(first: int, meal: int) -> dict[int, int]:
        """Latest start of stops first..meal-1, each leaving time for those after it."""
        out, following = {}, starts[meal]
        for i in range(meal - 1, first - 1, -1):
            pid, _start, close = order[i]
            following = min(following - legs[i] - visits[i], _last_start(roles[pid], close, visits[i]))
            out[i] = following
        return out

    first = 0
    meals = [i for i, (pid, _start, _close) in enumerate(order) if roles[pid] in ("lunch", "dinner")]
    for meal in meals:
        for i in range(first, meal):
            latest = latest_starts(first, meal)
            room = min(latest[j] - earliest[j] for j in range(first, i + 1))
            visits[i] += max(0, min(room, stubs[order[i][0]].visit_max - visits[i]))
        for i, start in latest_starts(first, meal).items():
            starts[i] = max(earliest[i], start)
        first = meal + 1

    out = []
    for i, (pid, _start, close) in enumerate(order):
        stub, end = stubs[pid], starts[i] + visits[i]
        may_stretch = i >= first or i in meals
        if may_stretch and stub.visit_max > visits[i] and not (roles[pid] == "lunch" and rest_minutes):
            limit = starts[i] + stub.visit_max
            room = starts[i + 1] - legs[i] if i + 1 < len(order) else limit
            end = max(end, min(limit, room, close))
        out.append({"poi_id": pid, "start": hh(starts[i]), "end": hh(end)})
    return out
