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

An order is judged on the day it gives, not on its driving alone (`timing_cost`).
The shortest tour used to win even when it opened an 08:00 day with lunch at 11:00,
or left three hours between lunch and the next stop while the cafe sat right before
that lunch: the solver's objective has no word for dead time, and of two days with
the same stops it returned either. Dead minutes now cost a quarter of a minute of
driving each, and a place the traveller named counts as misplaced outside its
sensible hours (a pagoda after dark while the morning stood empty).
"""

from __future__ import annotations

from dataclasses import replace

from BE.common import hhmm, to_min
from BE.app.services.soft_rules import (
    CAFE_AFTERNOON_START,
    CAFE_MORNING_END,
    DINNER_REQUIRED,
    LUNCH_REQUIRED,
    holds_lunch,
    meal_slot_at,
)

# Order search budget in visited nodes. Nine stops are searched exhaustively once
# the windows prune them; a count, not a clock, so the same plan comes back.
MAX_NODES = 150_000
# ... and in finished orders, each of which is timed and judged (`timing_cost`).
MAX_ORDERS = 4_000

# What a day may hold without it counting as dead time (minutes): a start this long
# after the trip's, a wait between two stops, and a rest after lunch this much over
# its length. Past that every minute costs TIMING_WEIGHT minutes of driving.
LATE_START_FREE = 30
HOLE_FREE = 30
REST_EXTRA_FREE = 45
# Measured on 219 real days (67 requests on danang-v1), same stops, weight only:
#   0     29.6 min driving a day, 17 days starting over an hour late, 37 holes
#   0.25  30.7 min                 0                                    8
#   0.5   30.9 min                 0                                    6
# A quarter buys nearly all of it for one more minute of driving a day.
TIMING_WEIGHT = 0.25
# A named place outside its sensible hours, in minutes of driving: worth a detour of
# up to half an hour to avoid, never worth dropping the place (the solver already
# seated it). On the 21 audited days with such a place, any value from 15 to 90 gave
# the same days: 6 of 27 named stops at a wrong hour became 1, for 2.6 minutes more
# driving a day (14 at most).
MISPLACED_COST = 30


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
    if role == "lunch_on_site":
        return clock if clock <= LUNCH_REQUIRED[0] else None
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
    elif role == "lunch_on_site":
        last = min(last, LUNCH_REQUIRED[0])
    return last


def held_to(stub, span: list[int]):
    """The stub with its windows cut so a visit can only START inside `span`."""
    windows = stub.windows or ((stub.open_min, stub.close_min),)
    return replace(stub, windows=tuple(
        (max(lo, span[0]), min(hi, span[1] + stub.visit_min))
        for lo, hi in windows if max(lo, span[0]) < min(hi, span[1] + stub.visit_min)))


def kept_dry(stub, wet: list[tuple[int, int]]):
    """The stub with the wet hours cut out of its windows: a stop the solver seated
    in a dry hour is not moved into the rain for a shorter drive."""
    windows = list(stub.windows or ((stub.open_min, stub.close_min),))
    for a, b in wet:
        windows = [piece for lo, hi in windows
                   for piece in ((lo, min(hi, a)), (max(lo, b), hi)) if piece[0] < piece[1]]
    return replace(stub, windows=tuple(windows)) if windows else stub


def timing_cost(rows: list[dict], legs: list[int], start_min: int, roles: dict,
                rest_minutes: int | None, preferred: dict | None = None) -> float:
    """What a finished day costs beyond its driving, in minutes of driving.

    `rows` are the day's stops with their final clock times, `legs` the minutes
    between consecutive stops (drive + the breathing room the model reserves).
    Dead time is a start later than LATE_START_FREE after the trip's and every wait
    past HOLE_FREE (after lunch: past the rest and REST_EXTRA_FREE). Time left after
    the last stop is free: the evening is the traveller's. `preferred[poi_id]` are the
    windows a named place should sit inside; outside all of them it is misplaced.
    """
    starts = [to_min(row["start"]) for row in rows]
    ends = [to_min(row["end"]) for row in rows]
    dead = max(0, starts[0] - start_min - LATE_START_FREE)
    for i, leg in enumerate(legs):
        free = HOLE_FREE
        if roles.get(rows[i]["poi_id"]) == "lunch" and rest_minutes:
            free = max(0, rest_minutes - leg) + REST_EXTRA_FREE
        dead += max(0, starts[i + 1] - ends[i] - leg - free)
    cost = TIMING_WEIGHT * dead
    for row, start, end in zip(rows, starts, ends):
        windows = (preferred or {}).get(row["poi_id"])
        if windows and not any(lo <= start and end <= hi for lo, hi in windows):
            cost += MISPLACED_COST
    return cost


def best_order(acts: list[dict], stubs: dict, travel: dict, start_min: int, end_min: int,
               overhead: int, rest_minutes: int | None = None, late_end_min: int | None = None,
               precedence: list | None = None, preferred: dict | None = None) -> list[dict] | None:
    """The stops in their best legal order with new clock times, None when the search
    cannot even rebuild the solver's own day (the caller keeps that one).

    Best = least driving plus `timing_cost` of the day the order gives. `preferred`:
    {poi_id: windows} a named place should sit inside when some order allows it.
    """
    ids = [a["poi_id"] for a in acts]
    if len(ids) < 2 or any(pid not in stubs for pid in ids):
        return None
    cafes = sum(1 for pid in ids if stubs[pid].category == "cafe")
    roles = {a["poi_id"]: _role(stubs[a["poi_id"]], to_min(a["start"]), cafes) for a in acts}
    if "lunch" not in roles.values():
        # No restaurant lunch: an all-day stop through the lunch window is where the
        # day eats (soft_rules.holds_lunch), and it must stay through that window.
        for act in acts:
            stub = stubs[act["poi_id"]]
            if not stub.restaurant and holds_lunch(to_min(act["start"]), to_min(act["start"]) + stub.visit_min):
                roles[act["poi_id"]] = "lunch_on_site"
                break
    before = {pid: {x for x, y in precedence or [] if y == pid and x in ids} for pid in ids}

    best: dict = {"cost": None, "rows": None}
    nodes = orders = 0

    def walk(order: list, clock: int, used: frozenset, spent: int, rest_until: int,
             slots: frozenset) -> None:
        nonlocal nodes, orders
        if nodes >= MAX_NODES or orders >= MAX_ORDERS:
            return
        # Driving so far is a floor on what any order from here costs.
        if best["cost"] is not None and spent >= best["cost"]:
            return
        if len(order) == len(ids):
            last_end = order[-1][1] + stubs[order[-1][0]].visit_min
            if late_end_min is None or last_end >= late_end_min:
                orders += 1
                rows = _close_gaps(order, stubs, roles, travel, overhead, rest_minutes)
                legs = [travel.get((order[i][0], order[i + 1][0]), 0) + overhead
                        for i in range(len(order) - 1)]
                cost = spent + timing_cost(rows, legs, start_min, roles, rest_minutes, preferred)
                if best["cost"] is None or cost < best["cost"]:
                    best["cost"], best["rows"] = cost, rows
            return
        prev = order[-1][0] if order else None
        for pid in ids:
            if pid in used or not before[pid] <= used:
                continue
            nodes += 1
            stub = stubs[pid]
            leg = 0
            if prev is not None:
                if stub.category and stub.category == stubs[prev].category:
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
            if roles[pid] == "lunch_on_site":
                # Through the whole lunch window: not so early that it ends before it does.
                earliest = max(earliest, LUNCH_REQUIRED[1] - stub.visit_min)
            placed = _place(stub, earliest, end_min)
            if placed is None or (roles[pid] and placed[0] > _last_start(roles[pid], placed[1], stub.visit_min)):
                continue
            start = placed[0]
            slot = meal_slot_at(start) if stub.restaurant else None
            if slot is not None and slot in slots:
                continue
            finish = start + stub.visit_min
            walk(order + [(pid, start, placed[1])], finish, used | {pid}, spent + leg,
                 finish + rest_minutes if (roles[pid] == "lunch" and rest_minutes) else rest_until,
                 slots | {slot} if slot is not None else slots)

    walk([], start_min, frozenset(), 0, 0, frozenset())
    return best["rows"]


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
        out.append({"poi_id": pid, "start": hhmm(starts[i]), "end": hhmm(end)})
    return out
