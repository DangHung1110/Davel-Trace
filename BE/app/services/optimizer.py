"""CP-SAT optimizer, OPTW (T017, lane B).

Model (OR-Tools CP-SAT):
- circuit over depot + POIs; self-arc[i][i] == "skip i".
- t[i] visit start; open[i] <= t[i] <= close[i]-dur[i] iff visited.
- arc[i][j] => t[j] >= t[i]+dur[i]+travel[i][j]; depot t[0]=trip start.
- An arc that rides a boat or cable car with a timetable also leaves in time for its
  last run and arrives no earlier than its first (`_transfer_rules`, transfers.py).
- Tmax: every visit finishes by trip end. Objective: max total score of visited.
Returns {"status": optimal|feasible-timeout|infeasible|unknown, "itinerary" | "reason", ...}.
Best-found is returned even on timeout. `unknown` = the search budget ran out before
any solution was found: the model was NOT proven infeasible, so a caller must not
read it as "these rules cannot be met".

A falsy `StubTrip.origin_id` selects the OPEN TOUR ("drop depot legs"): the origin leg
is not modelled, so the first activity may start at trip.start_min. A truthy one is
the place the day starts from (a lodging with a matrix row, or the stop a replan
resumes from): `travel[(origin_id, poi)]` is the first leg and an edge score keyed on
it prices arc 0 -> poi. `travel[(poi, origin_id)]`, when present (a day that starts at
the traveller's lodging, `profiles.build_plan`), is the ride back: objective v1 T9
prices it on arc poi -> 0, and no time is kept for it (the last visit only has to end
by the trip's end). Haversine is banned for feasibility (R4/B3): every leg,
the first one included, comes from the matrix.

Objective terms besides the score sum and the q_ij edge bonuses (T030):
- Category diversity: a distinct-category bonus plus a penalty on every visit beyond
  `CATEGORY_SOFT_CAP` of one category. Both scale with the TOP POI SCORE, so the term
  means the same for every profile (savings ~0.5, balanced ~5).
- A2: every pair of visited restaurants is penalized, whatever their hours (see the
  term: the time-distance version was never what the model charged).
- Dynamic state (trip_ctx): a per-band multiplier decides which hours suit a stop.
`STOP_OVERHEAD_MIN` minutes are reserved between stops in the MODEL only, so a day
cannot be crammed; reported visit end stays `start + visit_min`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from fractions import Fraction

from BE.app.services.soft_rules import (
    ALL_DAY_MIN,
    CAFE_AFTERNOON_START,
    CAFE_MAX_CAP,
    CAFE_MORNING_END,
    DINNER_REQUIRED,
    LUNCH_REQUIRED,
    MEAL_SLOTS,
    NON_FOOD_CAPPED,
    RESTAURANT_PAIR_MAX_GAP,
    cafe_daypart_at,
    category_allowed,
    clip_to_time_fit,
    holds_lunch,
    meal_slot_at,
    poi_category,
)
from BE.common import (
    access_charges, hhmm, own_fee, paid_access, poi_open_windows, to_min, trusted_rating)
from BE.app.services import objective as objective_mod
from BE.app.services import transfers as transfers_mod

TIMEOUT_S = 5.0

# T061a: must-go landmarks (snapshot `must_go`) get a small score nudge so
# they surface first. This is only a TIE-BREAK; the real guarantee is the
# HARD `must_visit` argument to optimize() (T053), which pins visit[i] == 1.
MUST_GO_BONUS = 0.5

# TASK-1: ONE tuning knob for the diversity term (0 = off). The two ratios
# are fixed fractions of the top POI score, so profile score scales keep
# their meaning (savings vs balanced vs experience).
DIVERSITY_WEIGHT = 1.0
DIVERSITY_PRESENCE_RATIO = 0.25   # per distinct category in the day
DIVERSITY_EXCESS_RATIO = 0.75     # per visit beyond CATEGORY_SOFT_CAP
CATEGORY_SOFT_CAP = 2
# Soft taste rules (exp/soft-rules-v2), in units of the top POI score like the
# diversity terms: a stop beyond the per-category daily cap costs half a top POI,
# a same-category arc a third of one. Design priors, to calibrate on gold/human review.
SOFT_CATEGORY_CAP_RATIO = 0.5
SOFT_CONSECUTIVE_RATIO = 0.3
# The seed walk (_greedy_hint): what is owed goes first once it is at most this many
# minutes away, and a leg is assumed to take at least this long.
HINT_READY_MIN = 30
HINT_MIN_LEG = 5
# A day that must end late and whose walk did not: how many evening stops are tried
# as the one kept back for the end (`_closers`), each a walk of about a millisecond.
HINT_CLOSER_TRIES = 3

# TASK-2: model-only breathing room between consecutive stops (minutes).
# Travel still comes from the matrix; the reserve is added on top, never
# substituted for it. It reduces effective density (a 660-min day fits ~8
# 60-min stops instead of 10-11) without touching reported visit length.
STOP_OVERHEAD_MIN = 12

# TASK-3: A2 objective weight, in units of the top POI score per close pair.
A2_PAIR_WEIGHT = 1.0

# DYNAMIC STATE (trip_ctx): weight of the time-banded state preference, in
# units of the top POI score. A multiplier of 0.2 costs ~3.2 * STATE_WEIGHT
# top-score units at that hour when BOTH probes land in the bad band (2 probes
# x (1-mult)/2), i.e. 0.5 * 3.2/0.8 ≈ 1.5 rating points -- enough to visibly
# re-order two stops of similar rating, never enough to beat the hard gate.
# 0.25 was too timid: satiety/heat/dip moved scores but rarely the ORDER, and
# the plan visibly kept a beach in the 14:00 dip. 0.5 is the tuned value
# (BE/tests/unit/test_state_scoring.py pins a rank-order flip at this weight).
STATE_WEIGHT = 0.5

# SOLUTION POOL (diverse select): enumerate up to N solutions inside a quality
# band of the optimum, then let pool.mmr_select pick pairwise-different plans.
POOL_DEFAULT_BAND = 0.95        # keep solutions >= 95 % of the OPT objective
POOL_ENUM_TIMEOUT_S = 25.0      # total budget for the enumeration pass
POOL_STEP_TIMEOUT_S = 5.0       # per member (nogood solve; warm greedy hint)
POOL_STEP_DETERMINISTIC_TIME = 2.0  # the same, in work units, when the caller plans by work

# CP-SAT settings of a search on a budget of work (`deterministic_time`). The default
# presolve runs three passes and full probing, about four work units on an 80-POI
# day: half of the old 8-unit budget went before the search improved on the seed.
# One pass and light probing leave that work to the search. Measured on 72 real
# models of danang-v1 against the best value known (reference: 24 units):
#   default, 8 units       98.2 % mean, 69 % worst, 5 models under 95 %; request 6.4 s median, 7.8 s p95
#   these,   5 units       99.3 % mean, 88 % worst, 1 model  under 95 %; request 5.7 s median, 6.1 s p95
# (a request = the slowest of its three profiles). One pass with the default probing,
# or this pair with symmetry detection off, left one day in 72 with no plan at 5
# units; this pair left none.
SEARCH_PRESOLVE_ITERATIONS = 1
SEARCH_PROBING_LEVEL = 1

# Completing the greedy hint (`_complete_hint`): a solve with the hinted variables
# fixed only has to derive the rest, so it ends in milliseconds; the limits are a
# guard, not a budget.
HINT_COMPLETE_DETERMINISTIC_TIME = 1.0
HINT_COMPLETE_WALL_S = 10.0
# Rescuing a search that had no seed and found nothing (`_repair_hint`): a second
# search of the same budget in which CP-SAT first moves the rejected seed until it is
# feasible. The conflict limit is how far it may move it (the default of 10 gave up
# on 2 of 9 real days, 2000 on none).
HINT_REPAIR_CONFLICTS = 2000


# What the model reads of a POI and of a trip (imported by profiles/replan).
@dataclass
class StubPOI:
    poi_id: str
    visit_min: int = 60
    open_min: int = 7 * 60
    close_min: int = 18 * 60
    score: float = 1.0
    restaurant: bool = False  # gate A1: <=1 restaurant per meal slot
    category: str = ""        # TASK-1: canonical category (cat/type); "" = legacy
    intensity: int = 2        # day-template effort ceiling (1..3)
    # Several opening windows (lunch + dinner service); () = the single
    # [open_min, close_min]. open/close then hold the envelope.
    windows: tuple[tuple[int, int], ...] = ()
    fee: int = 0              # VND per person (gate BCS, `max_fee`)
    visit_max: int = 0        # p75: how long a visit may run when the day has room
    # hours.kind == "by_booking": bookable sessions (cooking class); <= 1/day
    booking: bool = False
    group: str = ""           # objective v1 T3/T4 diversity group ("" = meal / unknown)
    zone: str = ""            # objective v1 T9 zone (a change of zone costs)
    # objective v1 T11 (objective.stub_keys): "" = none
    site: str = ""            # alt_group: one place under two records
    inside: str = ""          # the whole-area stop this one sits inside
    substitute: str = ""      # "day_market": a second one in the day costs
    dish: str = ""            # a restaurant's dish (mì Quảng twice costs)
    # Behind a boat or cable car with a timetable (POI `transfer`): a leg into or out
    # of it must catch a run (`transfers.leg_bounds`). None = reached by road / on foot.
    transfer: transfers_mod.Service | None = None
    # What reaching it costs besides `fee`, VND per person, each charge paid once a day
    # whoever needs it (BE.common.access_fees): ((key, vnd), ...). A key that is a stop's
    # poi_id is that stop's ticket: Cầu Vàng's Sun World ticket is not paid again when
    # the Sun World stop is in the day.
    access: tuple[tuple[str, int], ...] = ()


def _windows(poi: StubPOI) -> tuple[tuple[int, int], ...]:
    return poi.windows or ((poi.open_min, poi.close_min),)


def alone_fee(poi: StubPOI) -> int:
    """VND per person this stop costs when nothing else in the day shares its charges."""
    return poi.fee + sum(vnd for _key, vnd in poi.access)


def stubs_fee(stops) -> int:
    """VND per person of these stops: their fees and each access charge once, none for a
    charge whose key is one of the stops (the max_fee constraint, `BE.common.fee_breakdown`)."""
    ids = {stop.poi_id for stop in stops}
    extra: dict[str, int] = {}
    for stop in stops:
        for key, vnd in stop.access:
            if key not in ids:
                extra.setdefault(key, int(vnd))
    return sum(stop.fee for stop in stops) + sum(extra.values())


@dataclass
class StubTrip:
    start_min: int = 7 * 60
    end_min: int = 18 * 60
    origin_id: str = "depot"
    # The base itself sits behind a timetabled gateway (the Bà Nà summit hotel): its
    # first leg down rides the cable car, and a stop up there is a walk from it.
    origin_transfer: transfers_mod.Service | None = None


def poi_visit_min(poi: dict) -> int:
    """T061a adapter: schedule with p50 when the POI carries a VisitMin dict.

    The real snapshot stores `visit_min: {p25,p50,p75}` (R8: schedule p50,
    gate p75 buffer, UI the range). Legacy fixtures pass a flat int; both
    are accepted so old tests and live snapshots share one seam.
    """
    vm = poi.get("visit_min", 60)
    if isinstance(vm, dict):
        return int(vm.get("p50") or vm.get("p25") or 60)
    return int(vm or 60)


def poi_visit_short(poi: dict) -> int:
    """The shortest usual stay (p25): what a named place gets when nothing longer fits."""
    vm = poi.get("visit_min")
    if isinstance(vm, dict):
        return int(vm.get("p25") or poi_visit_min(poi))
    return poi_visit_min(poi)


def poi_visit_max(poi: dict) -> int:
    """How long people may stay when the day has room: p75, else the scheduled time."""
    vm = poi.get("visit_min")
    return int(vm.get("p75") or 0) if isinstance(vm, dict) else 0


def poi_windows(poi: dict, trip: dict | None = None,
                deadline: int | None = None,
                any_hour: bool = False) -> list[tuple[int, int]]:
    """T061a adapter: opening windows in minutes, trip window when unset.

    The windows are also cut to the hours the stop makes sense (TIME_FIT, a
    restaurant at a meal, a beach out of the midday sun) unless `any_hour`: the
    traveller named this very place, so only its opening hours bind.

    Opening hours stay authoritative (`open_windows`: overnight spans and
    every service of the day, intersected across weekday variants); a POI
    with none takes its category's measured SAFE_HOURS. Only a POI with
    neither (no hours, no `cat`) uses the trip window `[start_time,
    deadline]`; `deadline` (ETB: min(end, return)) wins over end_time when
    supplied so a horizon never silently stretches. No safe time gives
    [(0, 0)]: nothing fits.
    """
    wins = poi_open_windows(poi)
    if wins is not None:
        if not any_hour:
            wins = clip_to_time_fit(poi, wins)
        return wins or [(0, 0)]
    start = to_min((trip or {}).get("start_time", "07:00"))
    if deadline is not None:
        end = deadline
    else:
        end = to_min((trip or {}).get("end_time", "18:00"))
    return [(start, end)]


def poi_to_stub(poi: dict, trip: dict | None = None, score: float = 1.0,
                deadline: int | None = None, any_hour: bool = False,
                parent: dict | None = None) -> StubPOI:
    """T061a adapter: POI dict (snapshot or fixture) -> optimizer input.
    `parent`: the record its `requires_ticket_of` points to (objective v1 T11)."""
    wins = poi_windows(poi, trip, deadline, any_hour)
    bonus = MUST_GO_BONUS if poi.get("must_go") else 0.0
    category = poi_category(poi)
    return StubPOI(poi["poi_id"], poi_visit_min(poi), wins[0][0], wins[-1][1],
                   float(score) + bonus,
                   restaurant=category == "restaurant",
                   category=category,
                   intensity=int(poi.get("intensity") or 2),
                   windows=tuple(wins) if len(wins) > 1 else (),
                   fee=own_fee(poi, poi["poi_id"], paid_access(trip)) or 0,
                   visit_max=poi_visit_max(poi),
                   booking=(poi.get("hours") or {}).get("kind") == "by_booking",
                   transfer=transfers_mod.service(poi.get("transfer")),
                   access=stub_access(poi, paid_access(trip)),
                   **objective_mod.stub_keys(poi, parent))


def stub_access(poi: dict, paid=()) -> tuple[tuple[str, int], ...]:
    """`StubPOI.access` of a POI: its access charges the trip has not paid yet."""
    return tuple((c["key"], int(c["vnd"])) for c in access_charges(poi, paid))


def stubs_from_pois(pois: list[dict], trip: dict | None = None,
                    score_fn=None, deadline: int | None = None,
                    any_hour_ids: set[str] | None = None,
                    pois_by_id: dict | None = None) -> list[StubPOI]:
    """T061a adapter: adapt a POI list with one score function (or rating).
    `pois_by_id`: where a stop's whole-area parent is looked up (default: `pois`)."""
    def _score(p: dict) -> float:
        if score_fn is not None:
            return float(score_fn(p))
        return trusted_rating(p) or 1.0

    named = any_hour_ids or set()
    lookup = pois_by_id or {p["poi_id"]: p for p in pois}
    return [poi_to_stub(p, trip, _score(p), deadline, p["poi_id"] in named,
                        objective_mod.parent_of(p, lookup)) for p in pois]


def _hint_place(poi: StubPOI, prev_id: str | None, clock: int,
                trip: StubTrip, travel: dict[tuple[str, str], int],
                used_slots: set[int],
                blocked_window: tuple[int, int] | None = None,
                prev_transfer: transfers_mod.Service | None = None,
                ) -> tuple[int, int, int | None] | None:
    """(start, travel_min, meal_slot) for placing `poi`, or None if it cannot
    fit the matrix leg, opening window, free meal slot or locked rest window.
    A leg that rides a boat or cable car arrives when its timetable lets it
    (`prev_transfer`: the previous stop's, None after the base or a road stop)."""
    latest_start = None
    if prev_id is None and not trip.origin_id:
        leg = 0  # open tour: the origin leg is not modelled
        ready = clock
        if poi.transfer is not None:   # the day begins where the car or boat arrives
            lo, latest_start = transfers_mod.open_start(poi.transfer)
            ready = max(ready, lo)
    else:
        need = travel.get((prev_id or trip.origin_id, poi.poi_id))
        if need is None:
            return None  # B3: no matrix leg -> cannot be visited
        leg = need
        ready = clock + leg
        src = prev_transfer if prev_id is not None else trip.origin_transfer
        left, entered = transfers_mod.crossing(src, poi.transfer)
        if left is not None or entered is not None:
            arrive = transfers_mod.leg_arrival(clock, leg, left, entered)
            if arrive is None:
                return None  # the last car or boat of the leg has gone
            ready = arrive
    for open_min, close_min in _windows(poi):  # earliest window that fits
        close = min(close_min, trip.end_min)
        start = max(ready, open_min)
        # Locked rest window (day templates): the stop must finish before it or
        # start after it: never overlap.
        if blocked_window:
            lo, hi = blocked_window
            if start < hi and start + poi.visit_min > lo:
                start = max(start, hi)
        slot = meal_slot_at(start) if poi.restaurant else None
        if slot is not None and slot in used_slots:
            shifted = max(start, MEAL_SLOTS[slot][1])  # after the slot ends
            if shifted + poi.visit_min <= close:
                start = shifted
                slot = meal_slot_at(start)
        if slot is not None and slot in used_slots:
            continue  # A1: another restaurant already owns this meal slot
        if latest_start is not None and start > latest_start:
            continue
        if start + poi.visit_min <= close:
            return start, leg, slot
    return None


def _greedy_hint(pois: list[StubPOI], travel: dict[tuple[str, str], int],
                 trip: StubTrip,
                 must_set: set[str],
                 blocked_window: tuple[int, int] | None = None,
                 max_stops: int | None = None,
                 cafe_cap: int | None = None,
                 no_consecutive: bool = False,
                 no_adjacent_food: bool = False,
                 rest_after_lunch: int | None = None,
                 category_cap: int | None = None,
                 avoid_ids: set[str] | None = None,
                 precedence: list[tuple[str, str]] | None = None,
                 max_fee: int | None = None,
                 required_any: list[dict] | None = None,
                 lunch_required: bool = False,
                 dinner_required: bool = False,
                 state_bands: list[tuple[int, int]] | None = None,
                 state_cost: dict[tuple[str, int], float] | None = None,
                 late_end_min: int | None = None,
                 dup_free: frozenset = frozenset(),
                 objective: "objective_mod.Spec | None" = None,
                 _closer: int | None = None) -> list[tuple[int, int]]:
    """Deterministic feasible-ish tour used as a CP-SAT solution hint.

    Why: with the expanded candidate pool (all verified snapshot POIs) the
    single-worker search used by the T053 harness can burn the whole 5 s
    budget without proving feasibility, returning an empty plan. A greedy
    initial solution gives the solver a starting point; it never changes the
    model or the objective (hints are not constraints: an infeasible hint is
    simply ignored by CP-SAT).

    One forward walk, value per minute: among the stops that still fit (matrix leg +
    opening window + a free meal slot), take the best `(score + first-of-category
    bonus) / (idle wait + visit + overhead + leg)`. With one worker a seed that misses
    what the model demands can cost the whole budget (a tight day then has no plan),
    so the walk keeps room for it: must_visit in the asked order, lunch, dinner, the
    wishes (`required_any`), their money and their clock. What is owed and ready now
    goes first; a stop that would make something owed too late is not taken.
    TASK-1: at most `CATEGORY_SOFT_CAP` stops per category unless owed, so the seed
    already spreads across food/sightseeing/market. TASK-2: `STOP_OVERHEAD_MIN` is
    reserved between stops, exactly like the model. A must-visit stop the walk cannot place
    gives no hint at all. `state_cost` (rain on an open-air stop) is charged like the
    model charges it, and a stop worth nothing or less at that hour is left out unless
    it is owed. A seed blind to the rain opened the wet day at the beach, and the
    budget ended 38 % under the day the model wanted. `late_end_min` (a template's
    late end): a day that stopped at 19:17 was no day of the model at all, and with no
    seed the largest days got no plan inside the budget. The last stop is moved later
    inside its own hours until it ends late; when it cannot be (the walk had spent the
    money and the one landmark of the day by noon) the walk is redone with one evening
    stop kept back from the start (`_closer`, a node index): its category and its fee
    are held for it like a named place's, and it is seated once it can end late.

    Returns [(node_index, start_min), ...] or [].
    """
    if not pois:
        return []
    avoid = set(avoid_ids or ())
    node_of = {poi.poi_id: i for i, poi in enumerate(pois, 1)}
    must_left = {node_of[pid] for pid in must_set if pid in node_of}
    restaurants = {i for i, poi in enumerate(pois, 1) if poi.restaurant}
    cheapest_meal = min((alone_fee(pois[i - 1]) for i in restaurants), default=0)
    groups = []
    for req in required_any or []:
        named = req.get("poi_ids")
        cats = set(req.get("categories") or [])
        groups.append({"nodes": ({node_of[pid] for pid in named if pid in node_of} if named is not None
                                 else {i for i, poi in enumerate(pois, 1) if poi.category in cats}),
                       "need": int(req.get("count") or 1), "span": req.get("start_between"),
                       "named": named is not None})
    need_lunch, need_dinner = bool(lunch_required), bool(dinner_required)
    hint: list[tuple[int, int]] = []
    used_slots: set[int] = set()
    used_cats: dict[str, int] = {}
    restaurant_starts: list[int] = []
    cafe_starts: list[int] = []
    placed: set[int] = set()
    dup_keys: set[tuple[str, str]] = set()   # objective v1 T11 keys already in the seed
    previous: str | None = None
    previous_cat: str = ""
    previous_food = False
    clock = trip.start_min
    spent = 0
    # Access charges already in `spent`, and the stops seated (a parent seated is its
    # own ticket): what a further stop's charges cost the seed (`_charges`).
    bought: set[str] = set()

    def _charges(nodes, covered: set[str]) -> int:
        """VND the access charges of these nodes add, each once, beside `covered`."""
        covered = covered | {pois[j - 1].poi_id for j in nodes}
        extra: dict[str, int] = {}
        for j in nodes:
            for key, vnd in pois[j - 1].access:
                if key not in covered:
                    extra.setdefault(key, int(vnd))
        return sum(extra.values())

    def _clock_after(poi: StubPOI, start: int) -> int:
        """Advance the seed clock; lunch is followed by the rest window."""
        if (rest_after_lunch is not None and poi.restaurant
                and LUNCH_REQUIRED[0] <= start < LUNCH_REQUIRED[1]):
            return start + poi.visit_min + int(rest_after_lunch)
        return start + poi.visit_min + STOP_OVERHEAD_MIN

    def _duplicates(poi: StubPOI) -> bool:
        """Objective v1 T11 for the seed: a stop the objective charges as a near-duplicate
        of one already seated. Left to CP-SAT, a 5-unit search often kept such a seed
        (Chợ Hàn + Chợ Cồn, mì Quảng twice) instead of moving off it."""
        keys = _dup_keys(poi)
        if keys & dup_keys:
            return True
        if "umbrella" in dup_free:
            for j in placed:
                other = pois[j - 1]
                if (poi.inside and poi.inside in (other.poi_id, other.site)) or (
                        other.inside and other.inside in (poi.poi_id, poi.site)):
                    return True
        return False

    def _dup_keys(poi: StubPOI) -> set[tuple[str, str]]:
        return {(attr, getattr(poi, attr)) for attr in ("site", "substitute", "dish")
                if attr in dup_free and getattr(poi, attr)}

    def _blocked_by_cat(poi: StubPOI, start: int) -> bool:
        """CAFE_CAP / CATEGORY_CAP / NO_CONSECUTIVE / NO_ADJACENT_FOOD.

        Look-ahead for the seed only: the model carries the same rules as
        constraints, the hint just must not hand CP-SAT a start it has to undo.
        """
        if category_cap is not None and not category_allowed(
                poi.category, used_cats, category_cap):
            return True
        if no_consecutive and poi.category and poi.category == previous_cat:
            return True
        if no_adjacent_food and poi.restaurant and previous_food:
            return True
        if dup_free and poi.poi_id not in must_set and _duplicates(poi):
            return True
        if cafe_cap is not None and poi.category == "cafe":
            if len(cafe_starts) >= int(cafe_cap):
                return True
            if len(cafe_starts) == 1:
                # A 2nd cafe only across dayparts (same rule as the model): one in the
                # morning AND one in the afternoon. A first cafe at 12:45 is in neither,
                # so no second one can follow it (the seed used to seat one at 16:36).
                first, now = cafe_daypart_at(cafe_starts[0]), cafe_daypart_at(start)
                return first is None or now is None or now == first
        return False

    def _order_blocks(poi_id: str) -> bool:
        """An asked order: its first stop is still owed, or its second already went."""
        return any((then == poi_id and node_of.get(first) in must_left)
                   or (first == poi_id and node_of.get(then) in placed)
                   for first, then in precedence or [])

    def _leg(poi_id: str, nodes: set[int]) -> int:
        """The leg to a named place when it is known, else the shortest assumed."""
        if len(nodes) == 1:
            return travel.get((poi_id, pois[next(iter(nodes)) - 1].poi_id), HINT_MIN_LEG)
        return HINT_MIN_LEG

    def _feeds_lunch(poi: StubPOI) -> bool:
        """An all-day place that can still be where the day has its lunch."""
        return (need_lunch and not poi.restaurant and poi.visit_min >= ALL_DAY_MIN
                and poi.open_min <= LUNCH_REQUIRED[0])

    def _must_deadlines() -> dict[int, int]:
        """Latest start of each must_visit left, so that those after it still fit."""
        own = {i: min(pois[i - 1].close_min, trip.end_min) - pois[i - 1].visit_min for i in must_left}
        for i in must_left:
            ride = pois[i - 1].transfer
            if ride is not None and transfers_mod.crossing(trip.origin_transfer, ride)[1]:
                # Its car or boat stops arriving then (a walk from another stop up
                # there could start later; the seed does not count on it).
                own[i] = min(own[i], ride.go[1] + ride.ride)
            if _feeds_lunch(pois[i - 1]):
                # Started later it no longer runs through lunch, and no restaurant
                # can be reached from inside it.
                own[i] = min(own[i], LUNCH_REQUIRED[0])
        chain = sorted(must_left, key=lambda i: (own[i], i))
        for first, then in precedence or []:
            a, b = node_of.get(first), node_of.get(then)
            if a in own and b in own and chain.index(a) > chain.index(b):
                chain.remove(a)
                chain.insert(chain.index(b), a)
        latest: dict[int, int] = {}
        for at in range(len(chain) - 1, -1, -1):
            i = chain[at]
            latest[i] = own[i]
            if at + 1 < len(chain):
                after = chain[at + 1]
                latest[i] = min(own[i], latest[after] - pois[i - 1].visit_min - STOP_OVERHEAD_MIN
                                - _leg(pois[i - 1].poi_id, {after}))
        return latest

    unit = max((p.score for p in pois), default=1.0) or 1.0
    presence_value = unit * DIVERSITY_PRESENCE_RATIO
    late_end = (int(late_end_min) if late_end_min is not None and int(late_end_min) <= trip.end_min
                else None)
    closer_left = _closer is not None
    closer_span = _late_span(pois[_closer - 1], late_end, trip) if closer_left else None

    def _band_cost(poi: StubPOI, start: int) -> float:
        """What the model charges this stop for the band its middle falls in."""
        if not state_cost:
            return 0.0
        middle = start + poi.visit_min // 2
        for k, (lo, hi) in enumerate(state_bands or []):
            if lo <= middle < hi:
                return unit * float(state_cost.get((poi.poi_id, k), 0.0))
        return 0.0

    # Objective v1: a stop is worth what the objective pays for it there (T3-T9: its leg,
    # a repeat of its group, the meal it serves, one more pair of restaurants, the pace),
    # not the legacy first-of-category bonus the walk was written for. Blind to the
    # riding minutes, the walk gave savings days a seed below zero (legs cost 0.045U a
    # minute there) and the search spent its budget climbing out of it.
    used_groups: dict[str, int] = {}
    eaten: set[str] = set()
    sights = 0
    v1_meals = (objective_mod.meal_windows(objective, trip.start_min, trip.end_min)
                if objective is not None else [])

    def _v1_gain(poi: StubPOI, start: int, leg: int, wait: int) -> float:
        """T3-T9 of seating `poi` at `start` after the last stop, in U."""
        spec = objective
        gain = 0.0
        last = pois[node_of[previous] - 1] if previous is not None else None
        if last is not None or trip.origin_id:
            gain -= objective_mod.arc_cost(spec, leg, last.zone if last else "", poi.zone)
            if last is not None and poi.group and poi.group == last.group:
                gain -= spec.coef("gamma") * spec.beta(poi.group)
        seen = used_groups.get(poi.group, 0) if poi.group else 0
        if seen:
            rho = list(spec.w.get("rho") or [0.35, 0.7, 1.0])
            gain -= spec.beta(poi.group) * rho[min(seen - 1, len(rho) - 1)] * spec.coef("repeat_scale")
        if poi.restaurant:
            bonus = spec.w.get("meal_bonus") or {}
            if not poi.booking and wait <= HINT_READY_MIN:
                # The meal bonus only for a table ready now: counted after hours of
                # waiting, it made the walk skip a whole afternoon to sit at dinner.
                gain += spec.coef("meal_scale") * sum(
                    float(bonus.get(meal, 0.0)) for meal, lo, hi in v1_meals
                    if meal not in eaten and lo <= start < hi)
            gain -= len(restaurant_starts) * spec.meal_crowd()  # A2: one pair per earlier meal
        for attr, kind in (("site", "same_site"), ("substitute", "market"), ("dish", "dish")):
            if getattr(poi, attr) and (attr, getattr(poi, attr)) in seated_keys:
                gain -= spec.duplicate(kind)
        k0s = objective_mod.sight_k0(spec, trip.start_min, trip.end_min)
        if k0s is not None:
            windows = objective_mod.main_meals(spec, trip.start_min, trip.end_min)
            counted = sights + max(0, len(restaurant_starts) - windows)
            after = counted + (1 if not poi.restaurant or len(restaurant_starts) >= windows else 0)
            if after > k0s and after > counted:
                kappa = list(spec.w.get("kappa") or [0.3, 0.6, 1.0])
                gain -= kappa[min(after - k0s - 1, len(kappa) - 1)] * spec.coef("pace_scale")
        return gain

    seated_keys: set[tuple[str, str]] = set()

    while True:
        if max_stops is not None and len(hint) >= int(max_stops):
            break
        meal_window = (LUNCH_REQUIRED if need_lunch and clock < LUNCH_REQUIRED[1]
                       else DINNER_REQUIRED if need_dinner and clock < DINNER_REQUIRED[1] else None)
        open_groups = [g for g in groups if g["need"] > 0]
        # (latest start, the nodes that answer it) for what is owed by a clock.
        owed = [(when, {i}, "") for i, when in _must_deadlines().items()]
        owed += [(window[1], restaurants, meal) for window, needed, meal in (
            (LUNCH_REQUIRED, need_lunch, "lunch"), (DINNER_REQUIRED, need_dinner, "dinner")) if needed]
        owed += [(g["span"][1], g["nodes"], "") for g in open_groups if g["span"]]
        if closer_left:
            owed.append((closer_span[1], {_closer}, ""))
        owed = [row for row in owed if row[0] > clock]
        reserved = (len(must_left) + int(need_lunch) + int(need_dinner)
                    + sum(g["need"] for g in open_groups) + int(closer_left))
        best: tuple[tuple, int, int, int | None] | None = None
        closing_later: tuple[tuple, int, int, int | None] | None = None
        for i in range(1, len(pois) + 1):
            if i in placed:
                continue
            poi = pois[i - 1]
            if poi.poi_id in avoid or _order_blocks(poi.poi_id):
                continue
            mandatory = i in must_left
            closing = closer_left and i == _closer
            meal = meal_window if poi.restaurant else None
            span = next((g["span"] for g in open_groups if g["span"] and i in g["nodes"]), None)
            required = (mandatory or closing or meal is not None
                        or any(i in g["nodes"] for g in open_groups))
            if not required:
                if max_stops is not None and len(hint) + reserved >= int(max_stops):
                    continue
                if poi.category and used_cats.get(poi.category, 0) >= CATEGORY_SOFT_CAP:
                    continue
                # Its cap and the no-neighbour rules would then block the named place,
                # or the stop kept for the evening.
                kept = {pois[j - 1].category for j in must_left}
                if closer_left:
                    kept.add(pois[_closer - 1].category)
                if poi.category in kept:
                    continue
            if max_fee is not None and not mandatory:
                meals_after = int(need_lunch) + int(need_dinner) - (1 if meal else 0)
                owed_nodes = list(must_left) + ([_closer] if closer_left and not closing else [])
                held = sum(pois[j - 1].fee for j in owed_nodes) + meals_after * cheapest_meal
                # Its tickets / cano and those of what is owed, each once.
                held += _charges([i, *owed_nodes], bought)
                if spent + poi.fee + held > int(max_fee):
                    continue
            floor = max(clock, (meal or span or (clock,))[0])
            if closing:
                floor = max(floor, closer_span[0])
            spot = _hint_place(poi, previous, floor, trip, travel, used_slots,
                               blocked_window,
                               prev_transfer=pois[node_of[previous] - 1].transfer if previous else None)
            if spot is None:
                continue
            start, leg, slot = spot
            if (meal and start >= meal[1]) or (span and start >= span[1]):
                continue
            # An all-day stop through the lunch window is the lunch (eaten on site).
            feeds = need_lunch and not poi.restaurant and holds_lunch(start, start + poi.visit_min)
            if any(start + poi.visit_min + STOP_OVERHEAD_MIN + _leg(poi.poi_id, nodes) > when
                   for when, nodes, owes in owed
                   if i not in nodes and not (feeds and owes == "lunch")):
                continue
            # TASK-3: do not seed a <2.5h restaurant pair either.
            if poi.restaurant and not mandatory and any(
                    abs(start - other) < RESTAURANT_PAIR_MAX_GAP
                    for other in restaurant_starts):
                continue
            if _blocked_by_cat(poi, start):
                continue
            wait = start - clock
            value = poi.score - _band_cost(poi, start)
            if objective is not None:
                value += unit * _v1_gain(poi, start, leg, wait)
            elif poi.category and used_cats.get(poi.category, 0) == 0:
                value += presence_value  # reward a new category (TASK-1)
            if value <= 0 and not required:
                # Worth nothing to the objective: an open-air stop in the rain, or a
                # dear place the savings profile scores below zero. The model would
                # only take it for a rule the walk does not owe it to.
                continue
            minutes = wait + poi.visit_min + STOP_OVERHEAD_MIN + leg
            efficiency = value / max(1, minutes)
            # A wish that names its places ("hải sản": these 29 restaurants) is a
            # hard group in the wished rungs. Efficiency alone seated any
            # restaurant at lunch and dinner and left the group open, so the seed
            # broke a rule of the model and CP-SAT started from nothing: among the
            # stops ready now, one that closes such a group goes first.
            closes = sum(1 for g in open_groups if g["named"] and i in g["nodes"]
                         and (not g["span"] or g["span"][0] <= start < g["span"][1]))
            # A named all-day place goes before the short stops it would outlast:
            # by value per minute it always lost to a cafe, and then no longer fit.
            closes += int(mandatory and _feeds_lunch(poi))
            key = (not (required and wait <= HINT_READY_MIN), -closes, -efficiency,
                   -poi.score, poi.poi_id)
            if closing and wait > HINT_READY_MIN:
                # The stop kept for the evening closes the day: until its hour comes it
                # goes only when nothing else can (taken early on its value per minute,
                # it left a dinner that closes at 19:30 no time to start).
                closing_later = (key, i, start, slot)
                continue
            if best is None or key < best[0]:
                best = (key, i, start, slot)
        best = best or closing_later
        if best is None:
            break
        _key, i, start, slot = best
        poi = pois[i - 1]
        hint.append((i, start))
        spent += poi.fee + _charges([i], bought)
        bought.update(key for key, _vnd in poi.access)
        bought.add(poi.poi_id)
        placed.add(i)
        dup_keys.update(_dup_keys(poi))
        seated_keys.update((attr, getattr(poi, attr)) for attr in ("site", "substitute", "dish")
                           if getattr(poi, attr))
        must_left.discard(i)
        if i == _closer:
            closer_left = False
        if not poi.restaurant and holds_lunch(start, start + poi.visit_min):
            need_lunch = False
        if poi.restaurant:
            if need_lunch and LUNCH_REQUIRED[0] <= start < LUNCH_REQUIRED[1]:
                need_lunch = False
            elif need_dinner and DINNER_REQUIRED[0] <= start < DINNER_REQUIRED[1]:
                need_dinner = False
        for group in open_groups:
            if i in group["nodes"] and (not group["span"] or group["span"][0] <= start < group["span"][1]):
                group["need"] -= 1
        if slot is not None:
            used_slots.add(slot)
        if poi.restaurant:
            restaurant_starts.append(start)
            eaten.update(meal for meal, lo, hi in v1_meals if lo <= start < hi)
        else:
            sights += 1
        if poi.group:
            used_groups[poi.group] = used_groups.get(poi.group, 0) + 1
        if poi.category == "cafe":
            cafe_starts.append(start)
        if poi.category:
            used_cats[poi.category] = used_cats.get(poi.category, 0) + 1
        previous, previous_cat = poi.poi_id, poi.category
        previous_food = poi.restaurant
        clock = _clock_after(poi, start)

    def _ends_late(tour: list[tuple[int, int]]) -> bool:
        return any(start + pois[i - 1].visit_min >= late_end for i, start in tour)

    if hint and not must_left and late_end is not None and not _ends_late(hint):
        i, start = hint[-1]
        later = _ending_late(pois[i - 1], start, late_end, trip, blocked_window,
                             timed={n for g in groups if g["span"] for n in g["nodes"]}, node=i)
        if later is not None:
            hint[-1] = (i, later)
        elif _closer is None:
            # Keep one evening stop back from the start and walk the day again.
            for node in _closers(pois, late_end, trip, avoid, must_set, precedence, max_fee,
                                 cheapest_meal * (int(lunch_required) + int(dinner_required)),
                                 _band_cost)[:HINT_CLOSER_TRIES]:
                again = _greedy_hint(
                    pois, travel, trip, must_set, blocked_window=blocked_window, max_stops=max_stops,
                    cafe_cap=cafe_cap, no_consecutive=no_consecutive, no_adjacent_food=no_adjacent_food,
                    rest_after_lunch=rest_after_lunch, category_cap=category_cap, avoid_ids=avoid_ids,
                    precedence=precedence, max_fee=max_fee, required_any=required_any,
                    lunch_required=lunch_required, dinner_required=dinner_required,
                    state_bands=state_bands, state_cost=state_cost, late_end_min=late_end_min,
                    dup_free=dup_free, objective=objective,
                    _closer=node)
                if again and _ends_late(again):
                    return again
    return [] if must_left else hint


def _late_span(poi: StubPOI, late_end: int | None, trip: StubTrip) -> tuple[int, int] | None:
    """(earliest, latest) start at which this stop ends at or after `late_end` inside
    its own hours and the day, None when it never can."""
    if late_end is None:
        return None
    for open_min, close_min in _windows(poi):
        first = max(open_min, late_end - poi.visit_min)
        last = min(close_min, trip.end_min) - poi.visit_min
        if first <= last:
            return first, last
    return None


def _closers(pois: list[StubPOI], late_end: int, trip: StubTrip, avoid: set[str],
             must_set: set[str], precedence: list | None, max_fee: int | None,
             meals_fee: int, band_cost) -> list[int]:
    """Nodes that can close a day which must end late, best first.

    A stop that is no meal (meals and cafes keep their own hours and quotas), that the
    traveller did not name or order (those have their own place in the walk), that can
    end at or after `late_end`, and that the budget still affords beside the meals. By
    what it is worth at that hour (the rain counts), then by id.
    """
    ordered = {pid for pair in precedence or [] for pid in pair}
    rows = []
    for i, poi in enumerate(pois, 1):
        if (poi.restaurant or poi.category == "cafe" or poi.poi_id in avoid
                or poi.poi_id in must_set or poi.poi_id in ordered):
            continue
        span = _late_span(poi, late_end, trip)
        if span is None or (max_fee is not None and alone_fee(poi) + meals_fee > int(max_fee)):
            continue
        rows.append((-(poi.score - band_cost(poi, span[0])), poi.poi_id, i))
    return [i for _value, _pid, i in sorted(rows)]


def _ending_late(poi: StubPOI, start: int, late_end_min: int, trip: StubTrip,
                 blocked_window: tuple[int, int] | None, timed: set[int] | None = None,
                 node: int | None = None) -> int | None:
    """A later start for the day's LAST stop so that it ends at or after
    `late_end_min`, None when it already does or cannot inside its own hours.

    Only the last stop moves, so no leg behind it changes. It keeps what it was
    seated for: its meal slot (a dinner stays a dinner), its cafe daypart, and it
    does not move into a locked window. A stop that answers a timed wish stays.
    """
    if start + poi.visit_min >= late_end_min or (timed and node in timed):
        return None
    wanted = late_end_min - poi.visit_min
    for open_min, close_min in _windows(poi):
        later = max(wanted, open_min, start)
        if later + poi.visit_min > min(close_min, trip.end_min):
            continue
        if poi.restaurant and (meal_slot_at(later) != meal_slot_at(start)
                               or (DINNER_REQUIRED[0] <= start < DINNER_REQUIRED[1]) !=
                               (DINNER_REQUIRED[0] <= later < DINNER_REQUIRED[1])):
            continue
        if poi.category == "cafe" and cafe_daypart_at(later) != cafe_daypart_at(start):
            continue
        if blocked_window and later < blocked_window[1] and later + poi.visit_min > blocked_window[0]:
            continue
        return later
    return None


def _start_spans(windows, dur: int, first: int, last_end: int, literals) -> list:
    """[(earliest, latest, literal)]: the starts a visit can take inside each opening
    window, with the literal that puts it there (`visit` for one window, the window's
    pick for several). Reads the same bounds the model puts on t[i]: the window, the
    visit length and the day [first, last_end]. An empty span is a window too short
    for the visit: its literal can never hold."""
    return [(max(int(lo), first), min(int(hi), last_end) - dur, literal)
            for (lo, hi), literal in zip(windows, literals)]


def _window_hits(m, t, visit, i, lo: int, hi: int, tag: str, spans=None,
                 offset: int = 0):
    """Boolvar: node i is visited AND its start (t[i], or a probe `offset` minutes
    later) lies in [lo, hi).

    `spans` (`_start_spans`): when every opening window of the node starts its visits
    wholly inside or wholly outside [lo, hi), the hit IS the choice of a window, and
    no constraint on t[i] is needed. A restaurant open for lunch and for dinner is the
    usual case: its lunch hit is its lunch window. Reified on t[i], the hit is a pair
    of time disjunctions the search LP does not see; it then counts every meal bonus
    and meal-slot limit as free, and on a pool of many restaurants the search could
    not close that gap inside its budget (the 9 s request of
    `BE/tools/bench_latency.py`). A window that straddles a border is reified as before.
    """
    if spans is not None:
        inside, straddles = [], False
        for earliest, latest, literal in spans:
            first, last = earliest + offset, latest + offset
            if earliest > latest or last < lo or first >= hi:
                continue
            if lo <= first and last < hi:
                inside.append(literal)
            else:
                straddles = True
                break
        if not straddles:
            if len(inside) == 1:
                return inside[0]
            hit = m.NewBoolVar(f"{tag}_h_{i}")
            m.Add(hit == sum(inside))  # windows are exclusive: sum(picks) == visit
            return hit
    after, before = m.NewBoolVar(f"{tag}_a_{i}"), m.NewBoolVar(f"{tag}_b_{i}")
    hit = m.NewBoolVar(f"{tag}_h_{i}")
    m.Add(t[i] >= lo).OnlyEnforceIf(after)
    m.Add(t[i] < lo).OnlyEnforceIf(after.Not())
    m.Add(t[i] < hi).OnlyEnforceIf(before)
    m.Add(t[i] >= hi).OnlyEnforceIf(before.Not())
    m.AddMultiplicationEquality(hit, [after, before, visit[i]])
    return hit


def _complete_hint(m, cp_model):
    """Turn the partial greedy hint into a full feasible assignment; None if it has none.

    CP-SAT reads a hint only once presolve is done (with its defaults: 3 probing
    passes, ~3 work units on an 80-POI day; see `SEARCH_PRESOLVE_ITERATIONS`) and
    reports NOTHING when the budget ends before that: a short budget returned
    UNKNOWN for a day the hint already held. A solve with the hinted
    variables fixed fills in every other variable (they all follow from the arcs
    and clocks) and ends in milliseconds. Its solution becomes the complete hint,
    which the main search takes as its first incumbent, and the floor `optimize`
    returns when the search runs out of budget before improving on it. None when
    the greedy walk broke a rule the model has and the walk does not; the main
    search then starts from scratch as before.
    """
    probe = cp_model.CpSolver()
    probe.parameters.num_search_workers = 1
    probe.parameters.fix_variables_to_their_hinted_value = True
    probe.parameters.max_deterministic_time = HINT_COMPLETE_DETERMINISTIC_TIME
    probe.parameters.max_time_in_seconds = HINT_COMPLETE_WALL_S
    if probe.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    proto = m.proto if hasattr(m, "proto") else m.Proto()
    m.ClearHints()
    for index, value in enumerate(probe.ResponseProto().solution):
        proto.solution_hint.vars.append(index)
        proto.solution_hint.values.append(int(value))
    return probe


def _repair_hint(m, cp_model, budget: float, wall_s: float):
    """The best day a second search finds when it starts by repairing the rejected
    seed: the solver holding it, or None.

    The greedy walk does not know every rule of the model. A seed the model rejects
    leaves the search without an incumbent, and on the largest days it then found
    nothing inside the budget: the traveller got no plan at all (friends, 11 stops, a
    late end; 3 of 9 such solves, before the walk learnt the late end). CP-SAT's hint
    repair moves the seed until it is feasible and searches on from there. Used inside
    every search it cost up to a fifth of the objective on the days the plain search
    solved, so it is the rescue of a search that failed, not the way to search.
    """
    rescue = cp_model.CpSolver()
    rescue.parameters.num_search_workers = 1
    rescue.parameters.repair_hint = True
    rescue.parameters.hint_conflict_limit = HINT_REPAIR_CONFLICTS
    rescue.parameters.max_presolve_iterations = SEARCH_PRESOLVE_ITERATIONS
    rescue.parameters.cp_model_probing_level = SEARCH_PROBING_LEVEL
    rescue.parameters.max_deterministic_time = float(budget)
    rescue.parameters.max_time_in_seconds = float(wall_s)
    if rescue.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return rescue


def _overlap_hits(m, t, dur, visit, i, lo: int, hi: int, tag: str):
    """Boolvar: node i is visited AND [t, t+dur) overlaps [lo, hi)."""
    hit = m.NewBoolVar(f"{tag}_o_{i}")
    m.AddImplication(hit, visit[i])
    m.Add(t[i] < hi).OnlyEnforceIf(hit)
    m.Add(t[i] + dur[i] > lo).OnlyEnforceIf(hit)
    early = m.NewBoolVar(f"{tag}_e_{i}")       # not hit -> entirely before or after
    m.Add(t[i] + dur[i] <= lo).OnlyEnforceIf([visit[i], hit.Not(), early])
    m.Add(t[i] >= hi).OnlyEnforceIf([visit[i], hit.Not(), early.Not()])
    return hit


def _hint_dup_kinds(spec) -> frozenset:
    """T11 kinds the greedy seed keeps out (objective v1 only; a food tour keeps markets)."""
    if spec is None:
        return frozenset()
    kinds = {"site": "same_site", "umbrella": "umbrella", "substitute": "market",
             "dish": "dish"}
    return frozenset(attr for attr, kind in kinds.items() if spec.duplicate(kind) >= 1.0)


def _objective_v1_terms(m, spec, pois: list[StubPOI], ids: list[str], travel: dict,
                        trip: StubTrip, t: dict, visit: dict, arc: dict, unit: float,
                        slot_hits: dict, a1_hard: bool, rest_taken, tmax: int,
                        spans: dict | None = None):
    """Objective v1 terms T3-T9 (BE/app/services/objective.py), as one linear expression.

    Every coefficient is a weight in U times `unit * 1000`, the scale of the value
    term (`sco * 1000`), rounded to an integer like the rest of the model.
    """
    n = len(ids)
    scale = unit * 1000.0

    def k(weight: float) -> int:
        return int(round(scale * weight))

    expr = 0
    # T3: repeats inside a diversity group. y2, y3 then e (4th stop on) cost rho in
    # increasing order, so the solver always pays the cheapest one first.
    rho = list(spec.w.get("rho") or [0.35, 0.7, 1.0])
    groups: dict[str, list[int]] = {}
    for i in range(1, n + 1):
        if pois[i - 1].group:
            groups.setdefault(pois[i - 1].group, []).append(i)
    rep = spec.coef("repeat_scale")
    for g, nodes in groups.items():
        if len(nodes) < 2 or rep <= 0:
            continue
        beta = spec.beta(g) * rep
        y2 = m.NewBoolVar(f"rep2_{g}")
        parts = [(y2, rho[0])]
        if len(nodes) >= 3:
            y3 = m.NewBoolVar(f"rep3_{g}")
            parts.append((y3, rho[min(1, len(rho) - 1)]))
        if len(nodes) >= 4:
            e = m.NewIntVar(0, len(nodes), f"rep4_{g}")
            parts.append((e, rho[min(2, len(rho) - 1)]))
        m.Add(sum(v for v, _r in parts) >= sum(visit[i] for i in nodes) - 1)
        for v, r in parts:
            expr -= k(beta * r) * v
    # T4 + T9 on the arcs: a constant cost per used leg. With an origin the first leg
    # (0 -> j) and the ride back (i -> 0) cost what `travel` says; a ride back that is
    # not in it (a day that does not end at its start) costs nothing.
    gamma = spec.coef("gamma")
    origin = trip.origin_id or None
    for i in range(n + 1):
        for j in range(n + 1):
            if i == j or (i == 0 and j == 0):
                continue
            if (i == 0 or j == 0) and not origin:
                continue  # open tour: the depot legs are not modelled
            a = origin if i == 0 else ids[i - 1]
            b = origin if j == 0 else ids[j - 1]
            minutes = travel.get((a, b))
            cost = 0.0
            if minutes is not None:
                za = "" if i == 0 else pois[i - 1].zone
                zb = "" if j == 0 else pois[j - 1].zone
                cost += objective_mod.arc_cost(spec, int(minutes), za, zb)
            if i and j and pois[i - 1].group and pois[i - 1].group == pois[j - 1].group:
                cost += gamma * spec.beta(pois[i - 1].group)
            if cost:
                expr -= k(cost) * arc[(i, j)]
    # T5: a meal in each meal window the day spans.
    bonus = spec.w.get("meal_bonus") or {}
    meal_scale = spec.coef("meal_scale")
    food = [i for i in range(1, n + 1) if pois[i - 1].restaurant and not pois[i - 1].booking]
    for meal, lo, hi in objective_mod.meal_windows(spec, trip.start_min, tmax):
        weight = float(bonus.get(meal, 0.0)) * meal_scale
        if weight <= 0 or not food:
            continue
        hits = [_window_hits(m, t, visit, i, lo, hi, f"t5{meal}", (spans or {}).get(i))
                for i in food]
        z = m.NewBoolVar(f"meal_{meal}")
        m.Add(z <= sum(hits))
        expr += k(weight) * z
    # T6: a second restaurant in one meal slot (A1 when it is soft).
    crowd = spec.meal_crowd()
    if not a1_hard and crowd > 0:
        for idx, hits in slot_hits.items():
            if len(hits) > 1:
                extra = m.NewIntVar(0, len(hits), f"crowd_{idx}")
                m.Add(extra >= sum(hits) - 1)
                expr -= k(crowd) * extra
    # T7: the siesta right after lunch.
    if rest_taken is not None:
        expr += k(spec.rest_bonus()) * rest_taken
    # T11: near-duplicates, counted on the day (objective.duplicate_counts). A rule
    # the traveller made strict (`strict_rules`) is a constraint instead.
    def _extra(attr: str, kind: str, nodes_ok=lambda i: True):
        keyed: dict[str, list[int]] = {}
        for i in range(1, n + 1):
            key = getattr(pois[i - 1], attr, "")
            if key and nodes_ok(i):
                keyed.setdefault(key, []).append(i)
        rule = objective_mod.DUPLICATE_RULES[kind]
        weight = spec.duplicate(kind)
        out = 0
        for key, nodes in keyed.items():
            if len(nodes) < 2:
                continue
            if rule in spec.strict:
                m.Add(sum(visit[i] for i in nodes) <= 1)
                continue
            if weight <= 0:
                continue
            e = m.NewIntVar(0, len(nodes) - 1, f"dup_{kind}_{key}")
            m.Add(e >= sum(visit[i] for i in nodes) - 1)
            out -= k(weight) * e
        return out

    expr += _extra("site", "same_site")
    expr += _extra("substitute", "market")
    expr += _extra("dish", "dish", lambda i: not pois[i - 1].booking)
    inside: dict[int, list[int]] = {}
    for a, b in objective_mod.umbrella_pairs(pois):
        inside.setdefault(b + 1, []).append(a + 1)
    w_umb = spec.duplicate("umbrella")
    for b, areas in inside.items():
        if "SAME_SITE" in spec.strict:
            for a in areas:
                m.Add(visit[a] + visit[b] <= 1)
            continue
        if w_umb <= 0:
            continue
        u = m.NewBoolVar(f"dup_umbrella_{b}")
        for a in areas:
            m.Add(u >= visit[a] + visit[b] - 1)
        expr -= k(w_umb) * u
    # T8: stops beyond the comfortable count (objective.sight_k0 / paced_stops): the
    # sights, and the restaurants beyond one per meal window the day spans.
    sights = [i for i in range(1, n + 1) if not pois[i - 1].restaurant]
    meals = [i for i in range(1, n + 1) if pois[i - 1].restaurant]
    windows = objective_mod.main_meals(spec, trip.start_min, tmax)
    k0s = objective_mod.sight_k0(spec, trip.start_min, tmax)
    most = len(sights) + max(0, len(meals) - windows)
    if k0s is not None and spec.coef("pace_scale") > 0 and most > k0s:
        counted = sum(visit[i] for i in sights)
        if len(meals) > windows:
            extra_meals = m.NewIntVar(0, len(meals), "pace_meals")
            m.Add(extra_meals >= sum(visit[i] for i in meals) - windows)
            counted = counted + extra_meals
        kappa = list(spec.w.get("kappa") or [0.3, 0.6, 1.0])
        pace = spec.coef("pace_scale")
        s1 = m.NewBoolVar("pace_1")
        parts = [(s1, kappa[0])]
        if most > k0s + 1:
            s2 = m.NewBoolVar("pace_2")
            parts.append((s2, kappa[min(1, len(kappa) - 1)]))
        if most > k0s + 2:
            s3 = m.NewIntVar(0, n, "pace_3")
            parts.append((s3, kappa[min(2, len(kappa) - 1)]))
        m.Add(sum(v for v, _k in parts) >= counted - int(k0s))
        for v, kk in parts:
            expr -= k(pace * kk) * v
    return expr


def optimize(pois: list[StubPOI], travel: dict[tuple[str, str], int],
             trip: StubTrip, timeout_s: float = TIMEOUT_S,
             edge_scores: dict[tuple[str, str], float] | None = None,
             precedence: list[tuple[str, str]] | None = None,
             workers: int = 0,
             must_visit: list[str] | None = None,
             min_stops: int | None = None,
             max_stops: int | None = None,
             required_any: list[dict] | None = None,
             blocked_window: tuple[int, int] | None = None,
             rest_after_lunch: int | None = None,
             late_end_min: int | None = None,
             cafe_cap: int | None = None,
             no_consecutive: bool = False,
             no_adjacent_food: bool = False,
             lunch_required: bool = False,
             dinner_required: bool = False,
             state_bands: list[tuple[int, int]] | None = None,
             state_score: dict[tuple[str, int], float] | None = None,
             state_cost: dict[tuple[str, int], float] | None = None,
             category_cap: int | None = None,
             soft_category_cap: int | None = None,
             soft_no_consecutive: bool = False,
             diversity_weight: float | None = None,
             solution_pool: int = 1,
             pool_band: float = POOL_DEFAULT_BAND,
             pool_timeout_s: float | None = None,
             forbidden_sets: list[frozenset[str]] | None = None,
             distinct_from: list[frozenset[str]] | None = None,
             distinct_ceiling: float = 0.6,
             deterministic_time: float | None = None,
             not_first: set[str] | None = None,
             max_fee: int | None = None,
             objective: "objective_mod.Spec | None" = None) -> dict:
    """The best day over `pois` (see the module docstring for the model).

    edge_scores[(a, b)]: bonus when transition a->b is used.
    precedence[(A, B)]: when BOTH are visited, t[B] >= t[A]+dur[A].
    workers: 0 = solver default (wall-clock search, may vary run to run); 1 = a single
    deterministic worker.
    deterministic_time: search budget in OR-Tools work units (single worker). It stops
    after the same WORK on every run, where a wall-clock budget stops at whatever the
    machine reached; `timeout_s` still caps wall time.
    must_visit: HARD, every listed POI is in the itinerary (`MUST_GO_BONUS` is only a
    nudge). One outside the candidates, or that the horizon cannot fit, gives an honest
    no-solution rather than a plan that fails gate HCS.
    max_fee: HARD ceiling on the fee sum per person (gate BCS, SC-008), so a plan is
    never built over budget and then thrown away by the gate.
    not_first: POI ids that may not open the tour (a replan's next stop must not repeat
    the kind of stop just done).

    Day-template inputs (None = off):
    min_stops/max_stops: pace band on the number of visited POIs.
    required_any: [{"count": 1, "categories": [...]}]: at least `count` visits from each
    category set, or from its `poi_ids`, starting inside `start_between` when given (a
    missing set = honest infeasible, the caller relaxes or reports it).
    blocked_window: (lo, hi) minutes that NO visit may overlap (a replan after lunch).
    rest_after_lunch: siesta length in minutes, STARTING at the chosen lunch's END
    (REST_FOLLOWS_LUNCH); it implies a lunch. A late lunch makes the window run past the
    horizon, which simply leaves no room for more stops (the validator/report applies
    the 20-min floor and the shrink).
    late_end_min: at least one visit ends at/after it (friends-fast late end).

    Hard rules mirrored from the gate, so the solver avoids them instead of producing a
    plan the gate rejects (off by default, so the pure model tests keep their shape):
    cafe_cap: 1 = at most one cafe; 2 = at most two, one before 11:00 AND one after 13:00.
    no_consecutive: no arc between two POIs of the same category (a missing category is
    never "the same").
    no_adjacent_food: no arc between two restaurants, any cuisine. Redundant with
    no_consecutive today, explicit so the food rule survives a category split.
    lunch_required: a restaurant starts in 11:00-13:00, or an all-day stop (`ALL_DAY_MIN`)
    runs through that whole window and feeds its visitors on site. It is never relaxed.
    dinner_required: a restaurant starts in DINNER_REQUIRED. The planner may drop it, with
    a warning, when the money or the hours cannot hold a second meal.
    category_cap: at most N POIs per `NON_FOOD_CAPPED` category a day; meals are exempt.

    state_bands/state_score: dynamic state (trip_ctx). Disjoint time bands clipped to the
    horizon plus a per-(poi, band) multiplier; each band adds `unit * STATE_WEIGHT *
    (mult - 1)` when a visit lands in it. It steers placement (no beach in the 14:00 dip,
    no second meal right after lunch) without touching any hard rule.
    state_cost: per-(poi, band) cost in units of the top POI score, subtracted when a
    visit lands in the band (rain on an open-air stop, `trip_ctx.rain_costs`). Unlike the
    multiplier it may exceed what the stop is worth: the solver then leaves the stop out
    unless a hard rule (must_visit, a wish group, the pace floor) needs it.
    diversity_weight: overrides `DIVERSITY_WEIGHT` for this solve (the experience profile
    passes a dominant value, so a new category beats another stop of the same one).
    objective: objective v1 (`objective.Spec`). The taste rules become terms of the
    objective (T3-T9, see BE/app/services/objective.py): A1 and the siesta turn into
    penalties/bonuses unless `objective.strict` names them, the legacy diversity terms
    are replaced, and riding minutes, long legs and zone changes cost. None = legacy.

    solution_pool/pool_band/pool_timeout_s: enumerate up to `solution_pool` DISTINCT POI
    sets with objective >= `pool_band` * best, inside the enumeration budget. The result
    then carries `pool` [{activities, objective, poi_ids}] + `pool_stats`.
    forbidden_sets: pool-internal (`_pool_search`), one nogood per POI set already taken.
    distinct_from/distinct_ceiling: cross-option guarantee (router refill). The POI set A
    must keep Jaccard(A, S) <= `distinct_ceiling` for every S, i.e.
    |A&S| <= J*(|A|+|S|-|A&S|), which is LINEAR in the visit booleans: with J = p/q,
    (q+p)*|A&S| <= p*(|A|+|S|).
    """
    from ortools.sat.python import cp_model

    if int(solution_pool) > 1:
        # One pool = several full solves (fresh model each member): delegate
        # before building anything, so the single-plan path stays untouched.
        return _pool_search(
            pois, travel, trip, k=int(solution_pool), band=float(pool_band),
            budget=pool_timeout_s,
            kwargs=dict(timeout_s=timeout_s,
                        edge_scores=edge_scores, precedence=precedence,
                        workers=workers, must_visit=must_visit,
                        min_stops=min_stops,
                        max_stops=max_stops, required_any=required_any,
                        blocked_window=blocked_window,
                        rest_after_lunch=rest_after_lunch,
                        late_end_min=late_end_min, cafe_cap=cafe_cap,
                        no_consecutive=no_consecutive,
                        no_adjacent_food=no_adjacent_food,
                        lunch_required=lunch_required,
                        dinner_required=dinner_required,
                        state_bands=state_bands, state_score=state_score,
                        state_cost=state_cost,
                        category_cap=category_cap,
                        soft_category_cap=soft_category_cap,
                        soft_no_consecutive=soft_no_consecutive,
                        diversity_weight=diversity_weight,
                        distinct_from=distinct_from,
                        distinct_ceiling=distinct_ceiling, max_fee=max_fee,
                        deterministic_time=deterministic_time, not_first=not_first,
                        objective=objective))

    ids = [p.poi_id for p in pois]
    n = len(ids)
    must_set = set(must_visit or [])
    missing = sorted(must_set - set(ids))
    if missing:
        return {"status": "infeasible",
                "reason": f"must_visit ngoai candidate: {missing}",
                "elapsed_s": 0.0, "itinerary": None}

    node = {pid: i + 1 for i, pid in enumerate(ids)}  # 0 = depot
    dur = {0: 0, **{node[p.poi_id]: p.visit_min for p in pois}}
    opn = {0: trip.start_min, **{node[p.poi_id]: p.open_min for p in pois}}
    cls = {0: trip.end_min, **{node[p.poi_id]: p.close_min for p in pois}}
    sco = {i: (0.0 if i == 0 else pois[i - 1].score) for i in range(n + 1)}
    tmax = trip.end_min

    m = cp_model.CpModel()
    arc = {}
    for i in range(n + 1):
        for j in range(n + 1):
            tag = f"self_{i}" if i == j else f"arc_{i}_{j}"
            arc[(i, j)] = m.NewBoolVar(tag)
    # circuit: exactly one in/out per node (self-loop == skip)
    m.AddCircuit([(i, j, arc[(i, j)]) for i in range(n + 1) for j in range(n + 1)])
    t = {i: m.NewIntVar(trip.start_min, tmax, f"t_{i}") for i in range(n + 1)}
    m.Add(t[0] == trip.start_min)
    visit = {}
    spans = {}  # node -> where its start can lie, per opening window (_window_hits)
    for i in range(1, n + 1):
        visit[i] = m.NewBoolVar(f"visit_{i}")
        m.Add(arc[(i, i)] == 0).OnlyEnforceIf(visit[i])
        m.Add(arc[(i, i)] == 1).OnlyEnforceIf(visit[i].Not())
        if ids[i - 1] in must_set:
            # T053 bug 2: must_visit is HARD (gate HCS), not the soft bonus.
            m.Add(visit[i] == 1)
        wins = _windows(pois[i - 1])
        if len(wins) == 1:
            m.Add(opn[i] <= t[i]).OnlyEnforceIf(visit[i])
            m.Add(t[i] <= cls[i] - dur[i]).OnlyEnforceIf(visit[i])
            picks = [visit[i]]
        else:
            # Lunch + dinner service: a visit sits inside exactly one window.
            picks = []
            for k, (lo, hi) in enumerate(wins):
                pick = m.NewBoolVar(f"win_{i}_{k}")
                m.Add(lo <= t[i]).OnlyEnforceIf(pick)
                m.Add(t[i] <= hi - dur[i]).OnlyEnforceIf(pick)
                picks.append(pick)
            m.Add(sum(picks) == visit[i])
        m.Add(t[i] + dur[i] <= tmax).OnlyEnforceIf(visit[i])
        spans[i] = _start_spans(wins, dur[i], trip.start_min, tmax, picks)
    if max_fee is not None:
        spend = [pois[i - 1].fee * visit[i] for i in range(1, n + 1)]
        # What reaching a stop costs, once a day (BE.common.fee_breakdown): Cầu Vàng buys
        # the Sun World ticket unless the Sun World stop is in the day; Cù Lao Chàm the cano.
        needs: dict[str, list[int]] = {}
        amount: dict[str, int] = {}
        for i in range(1, n + 1):
            for key, vnd in pois[i - 1].access:
                needs.setdefault(key, []).append(i)
                amount.setdefault(key, int(vnd))
        for k, key in enumerate(sorted(needs)):
            pay = m.NewBoolVar(f"pay_{k}")
            covered = [visit[node[key]]] if key in node else []
            for i in needs[key]:
                m.AddBoolOr([visit[i].Not(), pay, *covered])   # visit and not covered -> pay
            spend.append(amount[key] * pay)
        m.Add(sum(spend) <= int(max_fee))

    # gate A1 (HARD): at most one restaurant per meal slot. The gate reads the
    # activity START, so membership is a function of t[i].
    slot_hits: dict[int, list] = {}
    booking_meal: dict[int, dict[int, object]] = {}   # slot -> {node: overlap hit}
    for i in range(1, n + 1):
        if pois[i - 1].booking:
            # cooking class: the session IS the meal of each slot it overlaps
            for idx, (lo, hi) in enumerate(MEAL_SLOTS):
                hit = _overlap_hits(m, t, dur, visit, i, lo, hi, f"bm_{idx}")
                booking_meal.setdefault(idx, {})[i] = hit
                slot_hits.setdefault(idx, []).append(hit)
            continue
        if not pois[i - 1].restaurant:
            continue
        for idx, (lo, hi) in enumerate(MEAL_SLOTS):
            slot_hits.setdefault(idx, []).append(
                _window_hits(m, t, visit, i, lo, hi, f"a1_{idx}", spans[i]))
    a1_hard = objective is None or "A1" in objective.strict
    for hits in slot_hits.values():
        if len(hits) > 1 and a1_hard:
            m.Add(sum(hits) <= 1)
    # by_booking (HARD): at most one session-based experience per day
    booked = [visit[i] for i in range(1, n + 1) if pois[i - 1].booking]
    if len(booked) > 1:
        m.Add(sum(booked) <= 1)

    # Universal lunch (human need): exactly one restaurant starts inside
    # 11:00-13:00: A1 above already caps the slot at one, so ">= 1" here is
    # "exactly one lunch". The same hits drive the rest window (below), which
    # is tied to the chosen lunch's END, not to a fixed 13:00 anchor.
    lunch_hits: list[tuple[int, object]] = []
    rest_hard = rest_after_lunch is not None and (
        objective is None or "REST_FOLLOWS_LUNCH" in objective.strict)
    rest_soft = rest_after_lunch is not None and not rest_hard
    if lunch_required or rest_after_lunch is not None:
        lunch_hits = [
            (i, _window_hits(m, t, visit, i, LUNCH_REQUIRED[0],
                             LUNCH_REQUIRED[1], "lunch", spans[i]))
            for i in range(1, n + 1) if pois[i - 1].restaurant and not pois[i - 1].booking
        ] + list(booking_meal.get(0, {}).items())   # a class over lunch is the lunch
        # An all-day place feeds its visitors (soft_rules.ALL_DAY_MIN): a stay that
        # runs through the whole lunch window is the lunch, with no rest to follow.
        on_site = []
        for i in range(1, n + 1):
            if pois[i - 1].restaurant or dur[i] < ALL_DAY_MIN:
                continue
            through = m.NewBoolVar(f"lunch_on_site_{i}")
            m.AddImplication(through, visit[i])
            m.Add(t[i] <= LUNCH_REQUIRED[0]).OnlyEnforceIf(through)
            m.Add(t[i] + dur[i] >= LUNCH_REQUIRED[1]).OnlyEnforceIf(through)
            on_site.append(through)
        if lunch_required or rest_hard:
            if not lunch_hits and not on_site:
                return {"status": "infeasible",
                        "reason": "khong co nha hang cho bua trua",
                        "elapsed_s": 0.0, "itinerary": None}
            m.Add(sum(hit for _i, hit in lunch_hits) + sum(on_site) >= 1)
    if dinner_required:
        dinner_hits = [_window_hits(m, t, visit, i, DINNER_REQUIRED[0],
                                    DINNER_REQUIRED[1], "dinner", spans[i])
                       for i in range(1, n + 1) if pois[i - 1].restaurant]
        if not dinner_hits:
            return {"status": "infeasible",
                    "reason": "khong co nha hang cho bua toi",
                    "elapsed_s": 0.0, "itinerary": None}
        m.Add(sum(dinner_hits) >= 1)

    # REST_FOLLOWS_LUNCH (HARD): rest_start == lunch_end for the chosen lunch,
    # and no other visit may overlap [rest_start, rest_start + rest_minutes).
    # The window may run past trip.end_min for a late lunch; then no stop can
    # start after it, which is exactly the horizon trim (report/validator
    # shrink the length, floor 20 min, and say so).
    # Objective v1 (rest_soft): the same window, but only when `rest_taken`, which
    # earns T7; a soft siesta needs a restaurant lunch to follow.
    rest_taken = None
    if rest_after_lunch is not None:
        cond = []
        if rest_soft:
            rest_taken = m.NewBoolVar("rest_taken")
            cond = [rest_taken]
            if lunch_hits:
                m.Add(sum(hit for _i, hit in lunch_hits) >= 1).OnlyEnforceIf(rest_taken)
            else:
                m.Add(rest_taken == 0)
        rest_start = m.NewIntVar(trip.start_min, tmax, "rest_start")
        for i, hit in lunch_hits:
            m.Add(rest_start == t[i] + dur[i]).OnlyEnforceIf([hit] + cond)
        rest_end = rest_start + int(rest_after_lunch)
        for i in range(1, n + 1):
            before = m.NewBoolVar(f"rest_b_{i}")
            m.Add(t[i] + dur[i] <= rest_start).OnlyEnforceIf(
                [visit[i], before] + cond)
            m.Add(t[i] >= rest_end).OnlyEnforceIf([visit[i], before.Not()] + cond)

    # gate CAFE_CAP (HARD): 1 cafe/day; a 2nd only across dayparts (morning
    # < 11:00 + afternoon > 13:00). The gate also requires the profile cafe
    # need; that is a caller decision (cafe_cap == 2), so the model only
    # enforces the daypart split and the absolute maximum of two.
    if cafe_cap is not None:
        cap = CAFE_MAX_CAP if int(cafe_cap) > 1 else 1
        cafes = [i for i in range(1, n + 1) if pois[i - 1].category == "cafe"]
        if len(cafes) > cap:
            m.Add(sum(visit[i] for i in cafes) <= cap)
        if cap == CAFE_MAX_CAP and len(cafes) > 1:
            morning = [_window_hits(m, t, visit, i, 0, CAFE_MORNING_END, "cam", spans[i])
                       for i in cafes]
            afternoon = [_window_hits(m, t, visit, i,
                                      CAFE_AFTERNOON_START + 1, 24 * 60, "caf", spans[i])
                         for i in cafes]
            m.Add(sum(morning) <= 1)
            m.Add(sum(afternoon) <= 1)
            two = m.NewBoolVar("cafe_two")
            m.Add(sum(visit[i] for i in cafes) >= 2).OnlyEnforceIf(two)
            m.Add(sum(visit[i] for i in cafes) <= 1).OnlyEnforceIf(two.Not())
            # Two cafes must be one morning + one afternoon (no 11:00-13:00).
            m.Add(sum(morning) >= 1).OnlyEnforceIf(two)
            m.Add(sum(afternoon) >= 1).OnlyEnforceIf(two)

    # gate CATEGORY_CAP (HARD): at most one non-food POI per category/day
    # (market/landmark/beach/attraction/temple/museum/park/viewpoint). Meals
    # stay on A1/CAFE_CAP. The gate reads the same `poi_category` values, so
    # the solver never produces a plan the gate rejects.
    if category_cap is not None:
        capped: dict[str, list[int]] = {}
        for i in range(1, n + 1):
            cat = pois[i - 1].category
            if cat in NON_FOOD_CAPPED:
                capped.setdefault(cat, []).append(i)
        for nodes in capped.values():
            if len(nodes) > int(category_cap):
                m.Add(sum(visit[i] for i in nodes) <= int(category_cap))

    # Pool-internal (see _pool_search): one nogood per accepted POI set
    # (`sum(visit) <= |S|-1`), so the next solve returns a DIFFERENT day.
    for forbidden in forbidden_sets or []:
        nodes = [node[pid] for pid in forbidden if pid in node]
        if len(nodes) == len(forbidden) and nodes:
            m.Add(sum(visit[i] for i in nodes) <= len(nodes) - 1)

    # Cross-option Jaccard ceiling (see docstring): a POI of S outside this
    # candidate list can never be shared, it only grows the union.
    if distinct_from:
        ceiling = Fraction(distinct_ceiling).limit_denominator(100)
        p, q = ceiling.numerator, ceiling.denominator
        visited = sum(visit[i] for i in range(1, n + 1))
        for other in distinct_from:
            nodes = [node[pid] for pid in other if pid in node]
            if nodes:
                m.Add((q + p) * sum(visit[i] for i in nodes)
                      <= p * (visited + len(other)))

    # gate NO_CONSECUTIVE (HARD): no arc between two same-category POIs.
    if no_consecutive:
        for i in range(1, n + 1):
            left = pois[i - 1].category
            if not left:
                continue
            for j in range(1, n + 1):
                if i != j and pois[j - 1].category == left:
                    m.Add(arc[(i, j)] == 0)

    # gate NO_ADJACENT_FOOD (HARD): no arc between two restaurants of ANY
    # cuisine. Kept separate from the category rule above (same effect today,
    # explicit intent, survives a future restaurant sub-categorisation).
    if no_adjacent_food:
        food = [i for i in range(1, n + 1) if pois[i - 1].restaurant]
        for i in food:
            for j in food:
                if i != j:
                    m.Add(arc[(i, j)] == 0)

    # --- day-template constraints (onboarding profile -> optimizer) --------
    # Pace band: the number of stops is a profile decision, not a solver one.
    if min_stops is not None:
        m.Add(sum(visit[i] for i in range(1, n + 1)) >= int(min_stops))
    if max_stops is not None:
        m.Add(sum(visit[i] for i in range(1, n + 1)) <= int(max_stops))
    # Archetype composition: at least N visits from each category set, or from
    # the exact POIs a narrow wish names ("hải sản": seafood places, not any meal).
    for position, req in enumerate(required_any or []):
        cats = set(req.get("categories") or [])
        named = req.get("poi_ids")
        nodes = ([node[pid] for pid in named if pid in node] if named is not None
                 else [i for i in range(1, n + 1) if pois[i - 1].category in cats])
        need = int(req.get("count") or 1)
        if len(nodes) < need:
            return {"status": "infeasible",
                    "reason": f"thieu loai {sorted(cats)} trong candidate",
                    "elapsed_s": 0.0, "itinerary": None}
        span = req.get("start_between")
        m.Add(sum(_window_hits(m, t, visit, i, int(span[0]), int(span[1]), f"wish{position}",
                               spans[i])
                  if span else visit[i] for i in nodes) >= need)
    # Locked rest window: a visited stop ends before it or starts after it.
    if blocked_window:
        lo, hi = int(blocked_window[0]), int(blocked_window[1])
        for i in range(1, n + 1):
            before = m.NewBoolVar(f"rest_b_{i}")
            m.Add(t[i] + dur[i] <= lo).OnlyEnforceIf([visit[i], before])
            m.Add(t[i] >= hi).OnlyEnforceIf([visit[i], before.Not()])
    # Late end: at least one visit ends at/after the template's late mark
    # (only passed when the trip horizon can contain it).
    if late_end_min is not None and int(late_end_min) <= tmax:
        late_vars = []
        for i in range(1, n + 1):
            late = m.NewBoolVar(f"late_{i}")
            m.Add(visit[i] == 1).OnlyEnforceIf(late)
            m.Add(t[i] + dur[i] >= int(late_end_min)).OnlyEnforceIf(late)
            late_vars.append(late)
        m.Add(sum(late_vars) >= 1)

    for i in range(n + 1):
        for j in range(1, n + 1):  # skip j == 0: return leg must not pin t[0]
            if i == j:
                continue
            if i == 0 and not trip.origin_id:
                # T061a "drop depot legs": open tour: the origin/hotel leg
                # is not modelled (seed has no depot node; adding one needs
                # an OSRM call and haversine is banned for feasibility).
                # The FIRST activity is therefore free to start at
                # trip.start_min; inter-POI arcs stay matrix-verified (B3).
                m.Add(t[j] >= t[i] + dur[i]).OnlyEnforceIf(arc[(i, j)])
                continue
            a, b = (trip.origin_id if i == 0 else ids[i - 1],
                    trip.origin_id if j == 0 else ids[j - 1])
            w = travel.get((a, b))
            if w is None:
                m.Add(arc[(i, j)] == 0)
            else:
                # TASK-2: breathing room only BETWEEN stops (i > 0); the
                # origin leg has none.
                gap = w + (STOP_OVERHEAD_MIN if i > 0 else 0)
                m.Add(t[j] >= t[i] + dur[i] + gap).OnlyEnforceIf(arc[(i, j)])
    _transfer_rules(m, t, dur, arc, ids, travel, trip, pois)
    for pid in not_first or ():
        if pid in node:
            m.Add(arc[(0, node[pid])] == 0)
    for prec in precedence or []:
        ia, ib = node.get(prec[0]), node.get(prec[1])
        if ia is not None and ib is not None:
            m.Add(t[ib] >= t[ia] + dur[ia]).OnlyEnforceIf(
                [visit[ia], visit[ib]])
    obj = sum(int(sco[i] * 1000) * visit[i] for i in range(1, n + 1))
    # The base a day starts from is the depot, not a stop: a score keyed on it prices
    # the first leg (arc 0 -> j), so the first drive costs what any other drive does.
    starts_at = ({**node, trip.origin_id: 0}
                 if trip.origin_id and trip.origin_id not in node else node)
    for (a, b), q in (edge_scores or {}).items():
        ia, ib = starts_at.get(a), node.get(b)
        if ia is not None and ib is not None and ia != ib:
            w_edge = 1.0 if objective is None else objective.coef("w_edge")
            obj += int(float(q) * 100 * w_edge) * arc[(ia, ib)]

    # TASK-1: category diversity. Terms are scaled by the top POI score so
    # one knob means the same thing for savings (~0.5) and balanced (~5).
    unit = max((p.score for p in pois), default=1.0)
    if unit <= 0:
        unit = 1.0
    div_weight = (DIVERSITY_WEIGHT if diversity_weight is None
                  else float(diversity_weight))
    if div_weight > 0 and objective is None:
        presence_bonus = int(unit * DIVERSITY_PRESENCE_RATIO
                             * div_weight * 1000)
        excess_penalty = int(unit * DIVERSITY_EXCESS_RATIO
                             * div_weight * 1000)
        by_cat: dict[str, list[int]] = {}
        for i in range(1, n + 1):
            if pois[i - 1].category:  # legacy fixtures: no category -> skip
                by_cat.setdefault(pois[i - 1].category, []).append(i)
        for cat, nodes in by_cat.items():
            count = m.NewIntVar(0, len(nodes), f"cat_n_{cat}")
            m.Add(count == sum(visit[i] for i in nodes))
            present = m.NewBoolVar(f"cat_p_{cat}")
            m.Add(count >= 1).OnlyEnforceIf(present)
            m.Add(count == 0).OnlyEnforceIf(present.Not())
            obj += presence_bonus * present
            if len(nodes) > CATEGORY_SOFT_CAP:
                excess = m.NewIntVar(0, len(nodes), f"cat_x_{cat}")
                m.Add(excess >= count - CATEGORY_SOFT_CAP)
                obj -= excess_penalty * excess

    # Soft taste rules: the per-category daily cap and the no-consecutive rule as
    # penalties instead of constraints (soft_rules.solver_taste_args). A second
    # beach or two temples in a row stay possible when they are worth the cost.
    if soft_category_cap is not None:
        cap_penalty = int(unit * SOFT_CATEGORY_CAP_RATIO * 1000)
        groups: dict[str, list[int]] = {}
        for i in range(1, n + 1):
            cat = pois[i - 1].category
            if cat in NON_FOOD_CAPPED:
                groups.setdefault(cat, []).append(i)
        for cat, nodes in groups.items():
            if len(nodes) > int(soft_category_cap):
                over = m.NewIntVar(0, len(nodes), f"soft_cap_{cat}")
                m.Add(over >= sum(visit[i] for i in nodes) - int(soft_category_cap))
                obj -= cap_penalty * over
    if soft_no_consecutive:
        consec_penalty = int(unit * SOFT_CONSECUTIVE_RATIO * 1000)
        for i in range(1, n + 1):
            left = pois[i - 1].category
            if not left:
                continue
            for j in range(1, n + 1):
                if i != j and pois[j - 1].category == left:
                    obj -= consec_penalty * arc[(i, j)]

    # TASK-3 (A2): what this term has charged since its first version is every PAIR
    # of visited restaurants, whatever their hours. Its "near" was `earlier OR later`
    # (t[j] - t[i] < GAP or t[i] - t[j] < GAP), true for any two starts, so a pair was
    # "close" as soon as both were visited, and a 12:00 lunch + 18:30 dinner paid it
    # too. The weights of objective v1 (meal_bonus.dinner 1.2 = 0.2 net of this pair)
    # were set on that behaviour, so it is kept here, written as what it is: the R
    # restaurants of a day cost R(R-1)/2 pairs. The time-distance rule the docs name
    # (`objective.features`, `soft_rules.plan_penalties` A2) is a separate decision.
    # As 5 booleans and 4 time disjunctions per pair (45 pairs on a pool of 10
    # restaurants) the search LP saw none of it: it priced every pair at zero and
    # could not close the gap inside its budget. A staircase over the count is exact
    # and in the LP (the k-th extra restaurant costs k pairs, cheapest first).
    restaurants = [i for i in range(1, n + 1) if pois[i - 1].restaurant]
    if len(restaurants) > 1:
        pair_penalty = int(unit * (A2_PAIR_WEIGHT if objective is None
                                   else objective.meal_crowd()) * 1000)
        if pair_penalty:
            extra = [m.NewBoolVar(f"a2_{k}") for k in range(1, len(restaurants))]
            m.Add(sum(extra) >= sum(visit[i] for i in restaurants) - 1)
            for k, step in enumerate(extra, start=1):
                obj -= pair_penalty * k * step
    # DYNAMIC STATE (trip_ctx): soft, time-banded preference. A stop's state
    # multiplier (satiety / fatigue / heat / dip / evening) is evaluated at
    # the midpoint of each disjoint band; the model then decides WHICH band
    # the stop lands in. That is what turns "avoid the beach at 14:00" from a
    # rank-time guess into a placement decision. Membership is probed at the
    # visit QUARTILES (t + dur/4 and t + 3*dur/4, averaged), not at its start,
    # so a 13:15 landmark that runs through the 13:30-15:00 dip cannot game
    # the band boundary with its midpoint. No band means no term (the
    # legacy/eval paths are unchanged).
    if state_bands and (state_score or state_cost):
        band_unit = int(unit * (STATE_WEIGHT if objective is None
                                else objective.coef("w_state")) * 1000)
        probes = []
        fractions = ((1, 4), (3, 4))
        for k, frac in enumerate(fractions):
            probe = {}
            for i in range(1, n + 1):
                probe[i] = m.NewIntVar(trip.start_min, tmax + 24 * 60,
                                       f"probe_{k}_{i}")
                m.Add(probe[i] == t[i] + dur[i] * frac[0] // frac[1]
                      ).OnlyEnforceIf(visit[i])
            probes.append(probe)
        for k, (lo, hi) in enumerate(state_bands):
            for i in range(1, n + 1):
                mult = (state_score or {}).get((ids[i - 1], k))
                cost = (state_cost or {}).get((ids[i - 1], k))
                if mult is None and cost is None:
                    continue
                delta = int(band_unit * (float(1.0 if mult is None else mult) - 1.0) / len(probes))
                # The rain cost has a weight of its own (objective `w_rain`, 1.0 = as
                # before), so a learned weights file can set it; the greedy seed keeps
                # charging the full cost (a seed only has to point the search).
                delta -= int(unit * 1000 * (1.0 if objective is None else objective.rain_weight())
                             * float(cost or 0.0) / len(probes))
                if not delta:
                    continue
                for probe, frac in zip(probes, fractions):
                    hit = _window_hits(m, probe, visit, i, int(lo), int(hi),
                                       f"state_{k}", spans[i],
                                       offset=dur[i] * frac[0] // frac[1])
                    obj += delta * hit
    if objective is not None:
        obj += _objective_v1_terms(m, objective, pois, ids, travel, trip, t, visit, arc,
                                   unit, slot_hits, a1_hard, rest_taken, tmax, spans)
    m.Maximize(obj)

    # Deterministic initial solution (see _greedy_hint): keeps the harness's
    # single-worker run feasible inside the 5 s budget. Hints are advisory.
    # Pool steps avoid one POI of every forbidden set, so the seed does not
    # reproduce a set the nogood just banned (must_visit is HARD: never drop).
    avoid_ids = ({next(iter(s)) for s in (forbidden_sets or []) if s}
                 - must_set)
    hint = _greedy_hint(pois, travel, trip, must_set,
                        blocked_window=blocked_window, max_stops=max_stops,
                        cafe_cap=cafe_cap,
                        no_consecutive=no_consecutive or soft_no_consecutive,
                        no_adjacent_food=no_adjacent_food,
                        rest_after_lunch=rest_after_lunch,
                        category_cap=(category_cap if category_cap is not None
                                      else soft_category_cap),
                        avoid_ids=avoid_ids,
                        precedence=precedence, max_fee=max_fee, required_any=required_any,
                        lunch_required=lunch_required, dinner_required=dinner_required,
                        state_bands=state_bands, state_cost=state_cost,
                        late_end_min=late_end_min,
                        dup_free=_hint_dup_kinds(objective), objective=objective)
    hint_solver = None
    if hint:
        previous = 0
        for i, start in hint:
            m.AddHint(arc[(previous, i)], 1)
            m.AddHint(t[i], start)
            previous = i
        if previous:
            m.AddHint(arc[(previous, 0)], 1)
        hinted = {i for i, _start in hint}
        for i in range(1, n + 1):
            if i not in hinted:
                m.AddHint(arc[(i, i)], 1)
        hint_solver = _complete_hint(m, cp_model)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_s
    if deterministic_time is not None:
        # Deterministic budget: the search stops after the same amount of WORK
        # on every run (single worker), so two eval runs cannot disagree just
        # because the machine was busier the second time.
        solver.parameters.num_search_workers = 1
        solver.parameters.max_deterministic_time = float(deterministic_time)
        solver.parameters.max_presolve_iterations = SEARCH_PRESOLVE_ITERATIONS
        solver.parameters.cp_model_probing_level = SEARCH_PROBING_LEVEL
    if workers:
        solver.parameters.num_search_workers = workers
    t0 = time.monotonic()
    status = solver.Solve(m)
    elapsed = time.monotonic() - t0
    name = solver.StatusName(status)
    from_hint = rescued = False
    if status == cp_model.UNKNOWN and hint_solver is not None:
        # The budget ended inside presolve: the completed hint is still a feasible
        # day of this very model, so it is the answer, not "nothing".
        solver, status, from_hint = hint_solver, cp_model.FEASIBLE, True
    elif status == cp_model.UNKNOWN and hint and deterministic_time is not None:
        # The model rejected the seed and the search found no day alone: once more,
        # this time starting by repairing that seed.
        rescue = _repair_hint(m, cp_model, float(deterministic_time), timeout_s)
        elapsed = time.monotonic() - t0
        if rescue is not None:
            solver, status, rescued = rescue, cp_model.FEASIBLE, True
    if status == cp_model.UNKNOWN:
        # Out of budget with no incumbent (the greedy hint was infeasible or the
        # budget did not even cover presolve). Not a proof of anything.
        return {"status": "unknown",
                "reason": "solver het ngan sach truoc khi tim duoc lich (UNKNOWN)",
                "elapsed_s": round(elapsed, 3), "itinerary": None}
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": "infeasible", "reason": f"solver {name}",
                "elapsed_s": round(elapsed, 3), "itinerary": None}
    def _take() -> tuple[list[int], list[dict]]:
        """Solution of the LAST Solve: node order + activities."""
        order, node_now = [], 0
        while True:
            nxt = next(j for j in range(n + 1)
                       if solver.Value(arc[(node_now, j)]))
            if nxt == 0:
                break
            order.append(nxt)
            node_now = nxt
        acts = [{"poi_id": ids[i - 1], "start": hhmm(int(solver.Value(t[i]))),
                 "end": hhmm(int(solver.Value(t[i])) + dur[i])}
                for i in order]
        return order, acts

    order, acts = _take()
    obj_value = solver.ObjectiveValue()
    return {"status": "optimal" if status == cp_model.OPTIMAL else "feasible-timeout",
            "from_hint": from_hint, "rescued": rescued,
            "elapsed_s": round(elapsed, 3),
            "itinerary": {"activities": acts,
                          "total_score": round(sum(sco[i] for i in order), 3),
                          "total_min": (int(solver.Value(t[order[-1]]))
                                        + dur[order[-1]] - trip.start_min) if order else 0},
            "objective": obj_value,
            "unit": unit,
            "rest_taken": (None if rest_taken is None else bool(solver.Value(rest_taken))),
            "pool": [{"activities": acts, "objective": round(obj_value, 3),
                      "poi_ids": [a["poi_id"] for a in acts]}],
            "pool_stats": {"requested": max(1, int(solution_pool)), "found": 1,
                           "band": float(pool_band),
                           "best_objective": round(obj_value, 3),
                           "floor_objective": round(obj_value, 3),
                           "best_status": ("optimal" if status == cp_model.OPTIMAL
                                           else "feasible-timeout"),
                           "elapsed_s": 0.0}}


def _pool_search(pois: list[StubPOI], travel: dict, trip: StubTrip,
                 k: int, band: float, budget: float | None,
                 kwargs: dict) -> dict:
    """Distinct-solution pool: argmax + banded nogood re-solves.

    Why not `enumerate_all_solutions`: it must run objective-free and
    single-threaded, and on this model (circuit + time windows + 48 POIs) it
    wanders the TIMING variables, yielding ~1 new POI set per 2 s. Why not a
    nogood loop on one solved model: mutating a solved circuit model and
    re-solving through the same CpSolver crashes OR-Tools 9.15 here (access
    violation), and a mutated model with a fresh solver crawls.

    So each member is a FRESH model + solve: cheap to build, crash-free,
    deterministic with workers=1, and optimisation-shaped, so the greedy hint
    keeps it fast. Member 0 is the plain argmax; each later member carries one
    nogood per accepted POI SET (`sum(visit) <= |S|-1`) and a hint that avoids
    one POI of every accepted set, so the search starts feasible and near the
    band.

    QUALITY BAND is a FILTER, not a constraint: a banded solve (floor inside
    the model) is a near-infeasibility problem that costs 4-5 s per member and
    often returns nothing, so members are generated as optima and then those
    below `band * argmax` are DROPPED. The stats say how many were generated
    (`found`) vs kept (`in_band`), so nobody can mistake a thin pool for a
    rich one.
    """
    base = {**kwargs, "solution_pool": 1}
    first = optimize(pois, travel, trip, **base)
    if first.get("itinerary") is None:
        return first
    argmax = float(first.get("objective") or 0.0)
    floor = argmax - (1.0 - float(band)) * max(1.0, abs(argmax))
    generated = list(first.get("pool") or [])
    sets: list[frozenset[str]] = [frozenset(generated[0]["poi_ids"])]
    allowed = float(budget) if budget is not None else POOL_ENUM_TIMEOUT_S
    by_work = base.get("deterministic_time") is not None
    t0 = time.monotonic()
    attempts = 0
    while len(sets) < int(k):
        left = allowed - (time.monotonic() - t0)
        if left <= 0.2 and not by_work:
            break
        attempts += 1
        # By work the pool is the same on a busy machine; the caller's wall guard in
        # `base` still stands behind each member.
        step = ({"deterministic_time": POOL_STEP_DETERMINISTIC_TIME} if by_work
                else {"timeout_s": max(0.5, min(POOL_STEP_TIMEOUT_S, left))})
        out = optimize(pois, travel, trip, **{**base, **step, "forbidden_sets": sets})
        member = (out.get("pool") or [None])[0]
        if out.get("itinerary") is None or not member:
            break  # the nogood neighbourhood is exhausted
        key = frozenset(member["poi_ids"])
        if key in sets:
            break
        sets.append(key)
        generated.append(member)
    kept = [it for it in generated
            if float(it["objective"]) >= floor - 1e-9]
    kept.sort(key=lambda it: -float(it["objective"]))
    first["pool"] = kept
    first["pool_stats"] = {
        "requested": int(k),
        "found": len(generated),
        "in_band": len(kept),
        "attempts": attempts,
        "band": float(band),
        "band_base_objective": round(argmax, 3),
        "best_objective": round(max(float(it["objective"])
                                    for it in generated), 3),
        "floor_objective": round(floor, 3),
        "best_status": (first.get("pool_stats") or {}).get("best_status"),
        "elapsed_s": round(time.monotonic() - t0, 3),
    }
    return first


def _transfer_rules(m, t, dur, arc, ids: list[str], travel: dict, trip: StubTrip,
                    pois: list[StubPOI]) -> None:
    """Boat and cable-car timetables (transfers.py) on the arcs that ride them.

    An arc into the places behind a gateway, or out of them, is a leg with a car or a
    boat in it. It must leave by `latest` and arrives no earlier than the first run
    allows (`transfers.leg_bounds`); an arc no run can serve is dropped. The open tour
    has no first leg, so a stop behind a gateway that opens it starts while cars or
    boats arrive (`open_start`). The day's last stop up there still needs a run back
    unless the base is up there too: its window already ends at `leave_by`
    (hours.access_window), and the arc to the depot states it again.
    """
    n = len(ids)
    svc = {i: pois[i - 1].transfer for i in range(1, n + 1) if pois[i - 1].transfer is not None}
    base = trip.origin_transfer if trip.origin_id else None
    if not svc and base is None:
        return
    for i in range(n + 1):
        src = svc.get(i) if i else base
        for j in range(n + 1):
            if i == j:
                continue
            dst = svc.get(j) if j else None
            if src is None and dst is None:
                continue
            if j == 0:
                left = transfers_mod.crossing(src, base)[0]
                if i > 0 and left is not None:
                    m.Add(t[i] + dur[i] <= left.back[1] - left.board).OnlyEnforceIf(arc[(i, 0)])
                continue
            if i == 0 and not trip.origin_id:
                lo, hi = transfers_mod.open_start(dst)
                m.Add(t[j] >= lo).OnlyEnforceIf(arc[(0, j)])
                m.Add(t[j] <= hi).OnlyEnforceIf(arc[(0, j)])
                continue
            w = travel.get((trip.origin_id if i == 0 else ids[i - 1], ids[j - 1]))
            if w is None:
                continue  # no matrix leg: the arc is already forbidden (B3)
            left, entered = transfers_mod.crossing(src, dst)
            if left is None and entered is None:
                continue  # a walk between two places behind one gateway
            latest, earliest, possible = transfers_mod.leg_bounds(w, left, entered)
            if not possible or (i == 0 and latest is not None and trip.start_min > latest):
                m.Add(arc[(i, j)] == 0)
                continue
            if i > 0 and latest is not None:
                m.Add(t[i] + dur[i] <= latest).OnlyEnforceIf(arc[(i, j)])
            if earliest is not None:
                m.Add(t[j] >= earliest).OnlyEnforceIf(arc[(i, j)])
