"""CP-SAT optimizer basic, OPTW (T017, lane B). Depot/flow/Tmax/windows.

STUB-NOTE: TripRequest/POI schemas (T007 trip/poi) are not in the lane-B
worktree yet â€” minimal STUB dataclasses below stand in (same field
names); phase-PR swaps them for the real schemas without touching the
model code. Travel comes from dict-of-dict minutes (T010 matrix).

Model (OR-Tools CP-SAT, 5s timeout):
- circuit over depot + POIs; self-arc[i][i] == "skip i".
- t[i] visit start; open[i] <= t[i] <= close[i]-dur[i] iff visited.
- arc[i][j] => t[j] >= t[i]+dur[i]+travel[i][j]; depot t[0]=trip start.
- Tmax: every visit finishes by trip end. Objective: max total score of visited.
Returns {"status": optimal|feasible-timeout|infeasible, "itinerary" |
"reason", ...}. Best-found is returned even on timeout (never empty-
handed when a feasible prefix exists).

T061a depot decision: `StubTrip.origin_id` is the depot (hotel). A falsy
origin (`""`/`None`) selects the OPEN-TOUR variant ("drop depot legs"):
the origin leg is not modelled, so the first activity may start at
trip.start_min. Chosen over "add a depot node to the matrix" because the
committed seed matrix has no depot cell and adding one needs a live OSRM
call (offline demo) â€” haversine is banned for feasibility (R4/B3). Every
INTER-POI transition still comes from the matrix; only the untracked
origin leg is dropped.

T030: optional q_ij edge bonuses + W_A+s_A<=W_B precedence (PATM).

TASK-1/2/3 objective additions (single-day plans):
- TASK-1 category diversity: the score sum is no longer the only term. A
  distinct-category presence bonus (spread across food/sightseeing/market/...)
  plus a linear penalty on every visit beyond `CATEGORY_SOFT_CAP` of the
  same category. Both are scaled by the TOP POI SCORE, so the term means the
  same thing for every profile (savings' scores are ~0.5, balanced's ~5) and
  `DIVERSITY_WEIGHT` is the single tuning knob (0 disables the term).
- TASK-2 pacing: `STOP_OVERHEAD_MIN` minutes are reserved between consecutive
  stops in the MODEL only (travel + overhead), so a day cannot be crammed
  with 9-10 back-to-back stops. Reported visit end stays `start + visit_min`
  (the reserve shows up as a real free gap; gate B3 still sees gap >= travel).
- TASK-3 A2 sharpening: every pair of restaurants closer than
  `RESTAURANT_PAIR_MAX_GAP` minutes (START-to-START) is penalized in the
  objective regardless of meal-slot labels, so the 10:49 / 11:00 case (A1
  passes, both are "one lunch") is caught by the solver, not just by review.

HARD sequence rules mirrored from the gate (opt-in params, so the pure model
tests keep their old shape):
- `cafe_cap`: at most N cafes (1 or 2); with 2, one must start before 11:00
  and the other after 13:00 (gate CAFE_CAP).
- `category_cap`: at most N non-food POIs per category per day (gate
  CATEGORY_CAP; N = 1 for every caller). Meals are exempt.
- `no_consecutive`: no arc between two same-category POIs (NO_CONSECUTIVE).
- `lunch_required`: exactly one restaurant starts in 11:00-13:00 (the
  universal lunch that the locked rest window follows).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from fractions import Fraction

from BE.app.services.common import hh, to_min
from BE.app.services.soft_rules import (
    CAFE_AFTERNOON_START,
    CAFE_MAX_CAP,
    CAFE_MORNING_END,
    CATEGORY_DAILY_CAP,
    LUNCH_REQUIRED,
    MEAL_SLOTS,
    NON_FOOD_CAPPED,
    RESTAURANT_PAIR_MAX_GAP,
    category_allowed,
    poi_category,
)
from BE.common import poi_open_windows

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


# ponytail: STUB dataclasses are a deliberate ceiling â€” T007 poi/trip
# schemas are not in this worktree; phase-PR swaps them in, model code
# untouched. Same field names, shared from here (imported by profiles/replan).
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


def _windows(poi: StubPOI) -> tuple[tuple[int, int], ...]:
    return poi.windows or ((poi.open_min, poi.close_min),)


@dataclass
class StubTrip:
    start_min: int = 7 * 60
    end_min: int = 18 * 60
    origin_id: str = "depot"


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


def poi_windows(poi: dict, trip: dict | None = None,
                deadline: int | None = None) -> list[tuple[int, int]]:
    """T061a adapter: opening windows in minutes, trip window when unset.

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
        return wins or [(0, 0)]
    start = to_min((trip or {}).get("start_time", "07:00"))
    if deadline is not None:
        end = deadline
    else:
        end = to_min((trip or {}).get("end_time", "18:00"))
    return [(start, end)]


def poi_window(poi: dict, trip: dict | None = None,
               deadline: int | None = None) -> tuple[int, int]:
    """Envelope of `poi_windows`: first opening to last closing."""
    wins = poi_windows(poi, trip, deadline)
    return wins[0][0], wins[-1][1]


def poi_to_stub(poi: dict, trip: dict | None = None, score: float = 1.0,
                deadline: int | None = None) -> StubPOI:
    """T061a adapter: POI dict (snapshot or fixture) -> optimizer input."""
    wins = poi_windows(poi, trip, deadline)
    bonus = MUST_GO_BONUS if poi.get("must_go") else 0.0
    category = poi_category(poi)
    return StubPOI(poi["poi_id"], poi_visit_min(poi), wins[0][0], wins[-1][1],
                   float(score) + bonus,
                   restaurant=category == "restaurant",
                   category=category,
                   intensity=int(poi.get("intensity") or 2),
                   windows=tuple(wins) if len(wins) > 1 else ())


def stubs_from_pois(pois: list[dict], trip: dict | None = None,
                    score_fn=None, deadline: int | None = None) -> list[StubPOI]:
    """T061a adapter: adapt a POI list with one score function (or rating)."""
    def _score(p: dict) -> float:
        if score_fn is not None:
            return float(score_fn(p))
        return float(p.get("rating") or 1.0)

    return [poi_to_stub(p, trip, _score(p), deadline) for p in pois]


def travel_from_matrix(matrix, ids=None):
    """T017 wiring: build optimize()'s travel dict from the cached matrix.

    `matrix` is MatrixService-compatible (needs .ids and .minutes_or_none).
    Pairs missing from the artifact stay ABSENT (arc forbidden in the model â€”
    B3: infeasible stays infeasible, never 0/haversine/estimate). POI-metadata
    adaptation (visit_min/opening-hours) stays in T061a, not here.
    """
    ids = list(matrix.ids) if ids is None else list(ids)
    travel = {}
    for a in ids:
        for b in ids:
            if a == b:
                continue
            m, _src = matrix.minutes_or_none(a, b)
            if m is not None:
                travel[(a, b)] = m
    return travel


def _hint_place(poi: StubPOI, prev_id: str | None, clock: int,
                trip: StubTrip, travel: dict[tuple[str, str], int],
                used_slots: set[int],
                blocked_window: tuple[int, int] | None = None,
                ) -> tuple[int, int, int | None] | None:
    """(start, travel_min, meal_slot) for placing `poi`, or None if it cannot
    fit the matrix leg, opening window, free meal slot or locked rest window."""
    if prev_id is None and not trip.origin_id:
        leg = 0  # open tour: the origin leg is not modelled
    else:
        need = travel.get((prev_id or trip.origin_id, poi.poi_id))
        if need is None:
            return None  # B3: no matrix leg -> cannot be visited
        leg = need
    for open_min, close_min in _windows(poi):  # earliest window that fits
        close = min(close_min, trip.end_min)
        start = max(clock + leg, open_min)
        # Locked rest window (day templates): the stop must finish before it or
        # start after it â€” never overlap.
        if blocked_window:
            lo, hi = blocked_window
            if start < hi and start + poi.visit_min > lo:
                start = max(start, hi)
        slot = _meal_slot_min(start) if poi.restaurant else None
        if slot is not None and slot in used_slots:
            shifted = max(start, MEAL_SLOTS[slot][1])  # after the slot ends
            if shifted + poi.visit_min <= close:
                start = shifted
                slot = _meal_slot_min(start)
        if slot is not None and slot in used_slots:
            continue  # A1: another restaurant already owns this meal slot
        if start + poi.visit_min <= close:
            return start, leg, slot
    return None


def _greedy_hint(pois: list[StubPOI], travel: dict[tuple[str, str], int],
                 trip: StubTrip,
                 must_set: set[str],
                 overhead_min: int = STOP_OVERHEAD_MIN,
                 blocked_window: tuple[int, int] | None = None,
                 max_stops: int | None = None,
                 cafe_cap: int | None = None,
                 no_consecutive: bool = False,
                 no_adjacent_food: bool = False,
                 rest_after_lunch: int | None = None,
                 category_cap: int | None = None,
                 avoid_ids: set[str] | None = None) -> list[tuple[int, int]]:
    """Deterministic feasible-ish tour used as a CP-SAT solution hint.

    Why: with the expanded candidate pool (all verified snapshot POIs) the
    single-worker search used by the T053 harness can burn the whole 5 s
    budget without proving feasibility, returning an empty plan. A greedy
    initial solution gives the solver a starting point; it never changes the
    model or the objective (hints are not constraints â€” an infeasible hint is
    simply ignored by CP-SAT).

    Order: must-visit POIs first (they are hard), then a value-per-minute
    greedy: among the stops that still fit (matrix leg + opening window + a
    free meal slot), pick the one with the best
    `(score + first-of-category bonus) / (idle wait + visit + overhead +
    leg)`. TASK-1: at most `CATEGORY_SOFT_CAP` non-mandatory stops per
    category, so the seed already spreads across food/sightseeing/market.
    TASK-2: `overhead_min` is reserved between stops, exactly like the model.
    A must-visit stop that cannot be placed means the model is infeasible
    anyway, so no hint is returned.

    Returns [(node_index, start_min), ...] or [].
    """
    if not pois:
        return []
    avoid = set(avoid_ids or ())
    must = sorted((i for i in range(1, len(pois) + 1)
                   if pois[i - 1].poi_id in must_set),
                  key=lambda i: (pois[i - 1].open_min,
                                 pois[i - 1].close_min, pois[i - 1].poi_id))
    hint: list[tuple[int, int]] = []
    used_slots: set[int] = set()
    used_cats: dict[str, int] = {}
    restaurant_starts: list[int] = []
    cafe_starts: list[int] = []
    placed: set[int] = set()
    previous: str | None = None
    previous_cat: str = ""
    previous_food = False
    clock = trip.start_min

    def _clock_after(poi: StubPOI, start: int) -> int:
        """Advance the seed clock; lunch is followed by the rest window."""
        if (rest_after_lunch is not None and poi.restaurant
                and LUNCH_REQUIRED[0] <= start < LUNCH_REQUIRED[1]):
            return start + poi.visit_min + int(rest_after_lunch)
        return start + poi.visit_min + overhead_min

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
        if cafe_cap is not None and poi.category == "cafe":
            if len(cafe_starts) >= int(cafe_cap):
                return True
            if len(cafe_starts) == 1:
                # A 2nd cafe only across dayparts (same rule as the model).
                return (cafe_daypart_min(start) is None
                        or cafe_daypart_min(start)
                        == cafe_daypart_min(cafe_starts[0]))
        return False

    for i in must:  # mandatory stops first, in opening-time order
        poi = pois[i - 1]
        spot = _hint_place(poi, previous, clock, trip, travel, used_slots,
                           blocked_window)
        if spot is None:
            return []  # mandatory stop does not fit: model is infeasible
        start, _leg, slot = spot
        if _blocked_by_cat(poi, start):
            return []  # seed cannot keep the hard sequence rules: let CP-SAT
        hint.append((i, start))
        placed.add(i)
        if slot is not None:
            used_slots.add(slot)
        if poi.restaurant:
            restaurant_starts.append(start)
        if poi.category == "cafe":
            cafe_starts.append(start)
        if poi.category:
            used_cats[poi.category] = used_cats.get(poi.category, 0) + 1
        previous, previous_cat = poi.poi_id, poi.category
        previous_food = poi.restaurant
        clock = _clock_after(poi, start)

    unit = max((p.score for p in pois), default=1.0) or 1.0
    presence_value = unit * DIVERSITY_PRESENCE_RATIO
    while True:
        if max_stops is not None and len(hint) >= int(max_stops):
            break
        best: tuple[tuple[float, float, str], int, int] | None = None
        for i in range(1, len(pois) + 1):
            if i in placed:
                continue
            poi = pois[i - 1]
            if poi.poi_id in avoid:
                continue
            if poi.category and used_cats.get(poi.category, 0) >= CATEGORY_SOFT_CAP:
                continue
            spot = _hint_place(poi, previous, clock, trip, travel, used_slots,
                               blocked_window)
            if spot is None:
                continue
            start, leg, _slot = spot
            # TASK-3: do not seed a <2.5h restaurant pair either.
            if poi.restaurant and any(
                    abs(start - other) < RESTAURANT_PAIR_MAX_GAP
                    for other in restaurant_starts):
                continue
            if _blocked_by_cat(poi, start):
                continue
            wait = start - clock
            value = poi.score
            if poi.category and used_cats.get(poi.category, 0) == 0:
                value += presence_value  # reward a new category (TASK-1)
            minutes = wait + poi.visit_min + overhead_min + leg
            efficiency = value / max(1, minutes)
            key = (-efficiency, -poi.score, poi.poi_id)
            if best is None or key < best[0]:
                best = (key, i, start)
        if best is None:
            break
        _key, i, start = best
        poi = pois[i - 1]
        spot = _hint_place(poi, previous, clock, trip, travel, used_slots,
                           blocked_window)
        _start, _leg, slot = spot
        hint.append((i, start))
        placed.add(i)
        if slot is not None:
            used_slots.add(slot)
        if poi.restaurant:
            restaurant_starts.append(start)
        if poi.category == "cafe":
            cafe_starts.append(start)
        if poi.category:
            used_cats[poi.category] = used_cats.get(poi.category, 0) + 1
        previous, previous_cat = poi.poi_id, poi.category
        previous_food = poi.restaurant
        clock = _clock_after(poi, start)
    return hint


def cafe_daypart_min(minutes: int) -> str | None:
    """Daypart of a cafe start in minutes (mirrors soft_rules.cafe_daypart)."""
    if minutes < CAFE_MORNING_END:
        return "morning"
    if minutes > CAFE_AFTERNOON_START:
        return "afternoon"
    return None


def _meal_slot_min(minutes: int) -> int | None:
    """Meal-slot index for a start in minutes (mirrors soft_rules.meal_slot)."""
    for idx, (lo, hi) in enumerate(MEAL_SLOTS):
        if lo <= minutes < hi:
            return idx
    return None


def _window_hits(m, t, visit, i, lo: int, hi: int, tag: str):
    """Boolvar: node i is visited AND its start lies in [lo, hi)."""
    after, before = m.NewBoolVar(f"{tag}_a_{i}"), m.NewBoolVar(f"{tag}_b_{i}")
    hit = m.NewBoolVar(f"{tag}_h_{i}")
    m.Add(t[i] >= lo).OnlyEnforceIf(after)
    m.Add(t[i] < lo).OnlyEnforceIf(after.Not())
    m.Add(t[i] < hi).OnlyEnforceIf(before)
    m.Add(t[i] >= hi).OnlyEnforceIf(before.Not())
    m.AddMultiplicationEquality(hit, [after, before, visit[i]])
    return hit


def optimize(pois: list[StubPOI], travel: dict[tuple[str, str], int],
             trip: StubTrip, require_all: bool = False,
             timeout_s: float = TIMEOUT_S,
             edge_scores: dict[tuple[str, str], float] | None = None,
             precedence: list[tuple[str, str]] | None = None,
             workers: int = 0,
             must_visit: list[str] | None = None,
             overhead_min: int | None = None,
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
             state_bands: list[tuple[int, int]] | None = None,
             state_score: dict[tuple[str, int], float] | None = None,
             category_cap: int | None = None,
             state_weight: float | None = None,
             diversity_weight: float | None = None,
             solution_pool: int = 1,
             pool_band: float = POOL_DEFAULT_BAND,
             pool_timeout_s: float | None = None,
             forbidden_sets: list[frozenset[str]] | None = None,
             distinct_from: list[frozenset[str]] | None = None,
             distinct_ceiling: float = 0.6,
             deterministic_time: float | None = None) -> dict:
    """T030: q_ij edge bonuses + W_A+s_A<=W_B precedence (both optional).

    edge_scores[(a, b)]: bonus added when transition a->b is used.
    precedence[(A, B)]: when BOTH visited, t[B] >= t[A]+dur[A].
    workers: 0 = solver default (wall-clock search, may vary run to run);
    1 = single deterministic worker, used by the T053 eval harness so a
    baseline comparison is reproducible.
    overhead_min: TASK-2 breathing room between stops (default
    `STOP_OVERHEAD_MIN`; 0 restores the old dense schedule, tests only).

    Day-template inputs (all optional, None = legacy behaviour):
    min_stops/max_stops: pace band on the number of visited POIs.
    required_any: [{"count": 1, "categories": [...]}] â€” at least `count`
    visits from each category set (a missing set = honest infeasible, the
    caller relaxes or reports it).
    blocked_window: (lo, hi) minutes that NO visit may overlap (legacy fixed
    locked rest; day templates now use `rest_after_lunch` instead).
    rest_after_lunch: siesta length in minutes, STARTING at the chosen lunch
    activity's END (REST_FOLLOWS_LUNCH). It implies `lunch_required`; no visit
    may overlap [lunch_end, lunch_end + rest_after_lunch). A late lunch makes
    the window run past the horizon, which simply leaves no room for more
    stops (the validator/report applies the 20-min floor and the shrink).
    late_end_min: at least one visit must end at/after it (friends-fast late
    end); the caller only passes it when the horizon can contain it.

    Hard sequence rules mirrored from the gate (so the solver avoids them
    instead of producing a plan the gate rejects):
    cafe_cap: None = legacy/off; 1 = at most one cafe; 2 = at most two, and
    only when one starts before 11:00 AND one after 13:00 (gate CAFE_CAP).
    no_consecutive: no arc between two POIs of the same category (gate
    NO_CONSECUTIVE); a missing category is never "the same".
    no_adjacent_food: no arc between two `restaurant` POIs, any cuisine (gate
    NO_ADJACENT_FOOD). It is redundant with NO_CONSECUTIVE today (both
    restaurants share the category) but it is kept explicit so the food rule
    survives a future category split, and so it holds even if the broader
    adjacency rule is turned off.
    lunch_required: at least one restaurant starts in 11:00-13:00, i.e. the
    universal lunch that the locked siesta follows (human need, every
    template). Kept out of `attempts()` â€” it is never relaxed.
    state_bands/state_score: DYNAMIC STATE soft layer (trip_ctx). Disjoint
    time bands clipped to the horizon, plus a per-(poi, band) multiplier;
    each band contributes `unit * STATE_WEIGHT * (mult - 1)` when a visit
    starts inside it. It steers placement (beach not at the 14:00 dip, no
    second meal right after lunch) without touching any hard rule.
    state_weight: override the module STATE_WEIGHT (tests pin the tuning).
    diversity_weight: override the module DIVERSITY_WEIGHT for this solve.
    The experience profile passes a dominant value so a new category beats
    another same-category stop; None keeps the global tuning.
    category_cap: HARD daily cap for `NON_FOOD_CAPPED` categories (gate
    CATEGORY_CAP). None = off (pure model tests); 1 = at most one market,
    landmark, beach, attraction, temple, museum, park or viewpoint per day.
    Meals are exempt (A1/CAFE_CAP own them).

    solution_pool/pool_band/pool_timeout_s: enumerate up to `solution_pool`
    DISTINCT POI sets whose objective is >= `pool_band` * best, inside a
    `pool_timeout_s` enumeration budget. The result then carries
    `pool` [{activities, objective, poi_ids}] + `pool_stats`; callers pick
    with pool.mmr_select (diverse mode). `solution_pool=1` (default) keeps the
    exact previous single-plan behaviour, including `elapsed_s`.

    forbidden_sets: pool-internal (see `_pool_search`). Each forbidden set is
    a POI set that must NOT be visited again: one nogood
    `sum(visit) <= |S|-1` per set, built into a FRESH model, never bolted onto
    a solved one.
    distinct_from/distinct_ceiling: cross-option guarantee (router refill).
    The returned POI set A must satisfy Jaccard(A, S) <= `distinct_ceiling`
    for every S, i.e. |A&S| <= J*(|A|+|S|-|A&S|), which is LINEAR in the visit
    booleans: (q+p)*|A&S| <= p*(|A|+|S|) with J = p/q exact. One solve
    replaces enumerating a pool and hoping a member clears the ceiling.
    deterministic_time: optional deterministic search budget (OR-Tools work
    units, single-worker). The T053 eval harness uses it instead of the plain
    wall clock so a published comparison is byte-reproducible: a wall-clock
    budget stops at whatever the machine reached, a deterministic budget stops
    after the same WORK on every run. `timeout_s` still caps wall time.

    must_visit (T053 bug 2): HARD constraint â€” every listed POI MUST be in
    the itinerary (visit[i] == 1), unlike the SOFT MUST_GO_BONUS nudge in
    poi_to_stub. A must_visit POI outside the candidate set, or one the
    horizon cannot fit, makes the model infeasible -> honest no_solution
    rather than a silently must-less plan that fails gate HCS.
    """
    from ortools.sat.python import cp_model

    if int(solution_pool) > 1:
        # One pool = several full solves (fresh model each member): delegate
        # before building anything, so the single-plan path stays untouched.
        return _pool_search(
            pois, travel, trip, k=int(solution_pool), band=float(pool_band),
            budget=pool_timeout_s,
            kwargs=dict(require_all=require_all, timeout_s=timeout_s,
                        edge_scores=edge_scores, precedence=precedence,
                        workers=workers, must_visit=must_visit,
                        overhead_min=overhead_min, min_stops=min_stops,
                        max_stops=max_stops, required_any=required_any,
                        blocked_window=blocked_window,
                        rest_after_lunch=rest_after_lunch,
                        late_end_min=late_end_min, cafe_cap=cafe_cap,
                        no_consecutive=no_consecutive,
                        no_adjacent_food=no_adjacent_food,
                        lunch_required=lunch_required,
                        state_bands=state_bands, state_score=state_score,
                        category_cap=category_cap, state_weight=state_weight,
                        diversity_weight=diversity_weight,
                        distinct_from=distinct_from,
                        distinct_ceiling=distinct_ceiling))

    overhead = STOP_OVERHEAD_MIN if overhead_min is None else int(overhead_min)
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
    for i in range(1, n + 1):
        visit[i] = m.NewBoolVar(f"visit_{i}")
        m.Add(arc[(i, i)] == 0).OnlyEnforceIf(visit[i])
        m.Add(arc[(i, i)] == 1).OnlyEnforceIf(visit[i].Not())
        if require_all:
            m.Add(visit[i] == 1)
        if ids[i - 1] in must_set:
            # T053 bug 2: must_visit is HARD (gate HCS), not the soft bonus.
            m.Add(visit[i] == 1)
        wins = _windows(pois[i - 1])
        if len(wins) == 1:
            m.Add(opn[i] <= t[i]).OnlyEnforceIf(visit[i])
            m.Add(t[i] <= cls[i] - dur[i]).OnlyEnforceIf(visit[i])
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
    # gate A1 (HARD): at most one restaurant per meal slot. The gate reads the
    # activity START, so membership is a function of t[i].
    slot_hits: dict[int, list] = {}
    for i in range(1, n + 1):
        if not pois[i - 1].restaurant:
            continue
        for idx, (lo, hi) in enumerate(MEAL_SLOTS):
            slot_hits.setdefault(idx, []).append(
                _window_hits(m, t, visit, i, lo, hi, f"a1_{idx}"))
    for hits in slot_hits.values():
        if len(hits) > 1:
            m.Add(sum(hits) <= 1)

    # Universal lunch (human need): exactly one restaurant starts inside
    # 11:00-13:00 â€” A1 above already caps the slot at one, so ">= 1" here is
    # "exactly one lunch". The same hits drive the rest window (below), which
    # is tied to the chosen lunch's END, not to a fixed 13:00 anchor.
    lunch_hits: list[tuple[int, object]] = []
    if lunch_required or rest_after_lunch is not None:
        lunch_hits = [
            (i, _window_hits(m, t, visit, i, LUNCH_REQUIRED[0],
                             LUNCH_REQUIRED[1], "lunch"))
            for i in range(1, n + 1) if pois[i - 1].restaurant
        ]
        if not lunch_hits:
            return {"status": "infeasible",
                    "reason": "khong co nha hang cho bua trua",
                    "elapsed_s": 0.0, "itinerary": None}
        m.Add(sum(hit for _i, hit in lunch_hits) >= 1)

    # REST_FOLLOWS_LUNCH (HARD): rest_start == lunch_end for the chosen lunch,
    # and no other visit may overlap [rest_start, rest_start + rest_minutes).
    # The window may run past trip.end_min for a late lunch; then no stop can
    # start after it, which is exactly the horizon trim (report/validator
    # shrink the length, floor 20 min, and say so).
    if rest_after_lunch is not None:
        rest_start = m.NewIntVar(trip.start_min, tmax, "rest_start")
        for i, hit in lunch_hits:
            m.Add(rest_start == t[i] + dur[i]).OnlyEnforceIf(hit)
        rest_end = rest_start + int(rest_after_lunch)
        for i in range(1, n + 1):
            before = m.NewBoolVar(f"rest_b_{i}")
            m.Add(t[i] + dur[i] <= rest_start).OnlyEnforceIf(
                [visit[i], before])
            m.Add(t[i] >= rest_end).OnlyEnforceIf([visit[i], before.Not()])

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
            morning = [_window_hits(m, t, visit, i, 0, CAFE_MORNING_END, "cam")
                       for i in cafes]
            afternoon = [_window_hits(m, t, visit, i,
                                      CAFE_AFTERNOON_START + 1, 24 * 60, "caf")
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
    # Archetype composition: at least N visits from each category set.
    for req in required_any or []:
        cats = set(req.get("categories") or [])
        nodes = [i for i in range(1, n + 1) if pois[i - 1].category in cats]
        need = int(req.get("count") or 1)
        if len(nodes) < need:
            return {"status": "infeasible",
                    "reason": f"thieu loai {sorted(cats)} trong candidate",
                    "elapsed_s": 0.0, "itinerary": None}
        m.Add(sum(visit[i] for i in nodes) >= need)
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
                # T061a "drop depot legs": open tour â€” the origin/hotel leg
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
                gap = w + (overhead if i > 0 else 0)
                m.Add(t[j] >= t[i] + dur[i] + gap).OnlyEnforceIf(arc[(i, j)])
    for prec in precedence or []:
        ia, ib = node.get(prec[0]), node.get(prec[1])
        if ia is not None and ib is not None:
            m.Add(t[ib] >= t[ia] + dur[ia]).OnlyEnforceIf(
                [visit[ia], visit[ib]])
    obj = sum(int(sco[i] * 1000) * visit[i] for i in range(1, n + 1))
    for (a, b), q in (edge_scores or {}).items():
        ia, ib = node.get(a), node.get(b)
        if ia is not None and ib is not None and ia != ib:
            obj += int(float(q) * 100) * arc[(ia, ib)]

    # TASK-1: category diversity. Terms are scaled by the top POI score so
    # one knob means the same thing for savings (~0.5) and balanced (~5).
    unit = max((p.score for p in pois), default=1.0)
    if unit <= 0:
        unit = 1.0
    div_weight = (DIVERSITY_WEIGHT if diversity_weight is None
                  else float(diversity_weight))
    if div_weight > 0:
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

    # TASK-3: A2 by TIME DISTANCE, not slot label. Any two visited
    # restaurants whose STARTs are < RESTAURANT_PAIR_MAX_GAP apart cost a
    # full stop's worth of objective (scaled by `unit`), so a 10:49 lunch
    # and an 11:00 lunch cannot both be paid for by their ratings even
    # though gate A1 (slot membership) sees only one restaurant.
    restaurants = [i for i in range(1, n + 1) if pois[i - 1].restaurant]
    if len(restaurants) > 1:
        pair_penalty = int(unit * A2_PAIR_WEIGHT * 1000)
        for pos, i in enumerate(restaurants):
            for j in restaurants[pos + 1:]:
                both = m.NewBoolVar(f"a2b_{i}_{j}")
                m.AddBoolAnd([visit[i], visit[j]]).OnlyEnforceIf(both)
                m.AddBoolOr([visit[i].Not(), visit[j].Not()]).OnlyEnforceIf(
                    both.Not())
                earlier = m.NewBoolVar(f"a2l_{i}_{j}")   # t[j] - t[i] < GAP
                m.Add(t[j] - t[i] <= RESTAURANT_PAIR_MAX_GAP - 1).OnlyEnforceIf(
                    earlier)
                m.Add(t[j] - t[i] >= RESTAURANT_PAIR_MAX_GAP).OnlyEnforceIf(
                    earlier.Not())
                later = m.NewBoolVar(f"a2g_{i}_{j}")     # t[i] - t[j] < GAP
                m.Add(t[i] - t[j] <= RESTAURANT_PAIR_MAX_GAP - 1).OnlyEnforceIf(
                    later)
                m.Add(t[i] - t[j] >= RESTAURANT_PAIR_MAX_GAP).OnlyEnforceIf(
                    later.Not())
                near = m.NewBoolVar(f"a2n_{i}_{j}")
                m.AddBoolOr([earlier, later]).OnlyEnforceIf(near)
                m.AddBoolAnd([earlier.Not(), later.Not()]).OnlyEnforceIf(
                    near.Not())
                close = m.NewBoolVar(f"a2c_{i}_{j}")
                m.AddBoolAnd([both, near]).OnlyEnforceIf(close)
                m.AddBoolOr([both.Not(), near.Not()]).OnlyEnforceIf(close.Not())
                obj -= pair_penalty * close
    # DYNAMIC STATE (trip_ctx): soft, time-banded preference. A stop's state
    # multiplier (satiety / fatigue / heat / dip / evening) is evaluated at
    # the midpoint of each disjoint band; the model then decides WHICH band
    # the stop lands in. That is what turns "avoid the beach at 14:00" from a
    # rank-time guess into a placement decision. Membership is probed at the
    # visit QUARTILES (t + dur/4 and t + 3*dur/4, averaged), not at its start,
    # so a 13:15 landmark that runs through the 13:30-15:00 dip cannot game
    # the band boundary with its midpoint. No band means no term (the
    # legacy/eval paths are unchanged).
    if state_bands and state_score:
        band_unit = int(unit * (STATE_WEIGHT if state_weight is None
                                else float(state_weight)) * 1000)
        probes = []
        for k, frac in enumerate(((1, 4), (3, 4))):
            probe = {}
            for i in range(1, n + 1):
                probe[i] = m.NewIntVar(trip.start_min, tmax + 24 * 60,
                                       f"probe_{k}_{i}")
                m.Add(probe[i] == t[i] + dur[i] * frac[0] // frac[1]
                      ).OnlyEnforceIf(visit[i])
            probes.append(probe)
        for k, (lo, hi) in enumerate(state_bands):
            for i in range(1, n + 1):
                mult = state_score.get((ids[i - 1], k))
                if mult is None:
                    continue
                delta = int(band_unit * (float(mult) - 1.0) / len(probes))
                if not delta:
                    continue
                for probe in probes:
                    hit = _window_hits(m, probe, visit, i, int(lo), int(hi),
                                       f"state_{k}")
                    obj += delta * hit
    m.Maximize(obj)

    # Deterministic initial solution (see _greedy_hint): keeps the harness's
    # single-worker run feasible inside the 5 s budget. Hints are advisory.
    # Pool steps avoid one POI of every forbidden set, so the seed does not
    # reproduce a set the nogood just banned (must_visit is HARD: never drop).
    avoid_ids = ({next(iter(s)) for s in (forbidden_sets or []) if s}
                 - must_set)
    hint = _greedy_hint(pois, travel, trip, must_set, overhead_min=overhead,
                        blocked_window=blocked_window, max_stops=max_stops,
                        cafe_cap=cafe_cap, no_consecutive=no_consecutive,
                        no_adjacent_food=no_adjacent_food,
                        rest_after_lunch=rest_after_lunch,
                        category_cap=category_cap, avoid_ids=avoid_ids)
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

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_s
    if deterministic_time is not None:
        # Deterministic budget: the search stops after the same amount of WORK
        # on every run (single worker), so two eval runs cannot disagree just
        # because the machine was busier the second time.
        solver.parameters.num_search_workers = 1
        solver.parameters.max_deterministic_time = float(deterministic_time)
    if workers:
        solver.parameters.num_search_workers = workers
    t0 = time.monotonic()
    status = solver.Solve(m)
    elapsed = time.monotonic() - t0
    name = solver.StatusName(status)
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
        acts = [{"poi_id": ids[i - 1], "start": hh(int(solver.Value(t[i]))),
                 "end": hh(int(solver.Value(t[i])) + dur[i])}
                for i in order]
        return order, acts

    order, acts = _take()
    objective = solver.ObjectiveValue()
    return {"status": "optimal" if status == cp_model.OPTIMAL else "feasible-timeout",
            "elapsed_s": round(elapsed, 3),
            "itinerary": {"activities": acts,
                          "total_score": round(sum(sco[i] for i in order), 3),
                          "total_min": (int(solver.Value(t[order[-1]]))
                                        + dur[order[-1]] - trip.start_min) if order else 0},
            "objective": objective,
            "pool": [{"activities": acts, "objective": round(objective, 3),
                      "poi_ids": [a["poi_id"] for a in acts]}],
            "pool_stats": {"requested": max(1, int(solution_pool)), "found": 1,
                           "band": float(pool_band),
                           "best_objective": round(objective, 3),
                           "floor_objective": round(objective, 3),
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
    t0 = time.monotonic()
    attempts = 0
    while len(sets) < int(k):
        left = allowed - (time.monotonic() - t0)
        if left <= 0.2:
            break
        attempts += 1
        out = optimize(pois, travel, trip,
                       **{**base,
                          "timeout_s": max(0.5, min(POOL_STEP_TIMEOUT_S, left)),
                          "forbidden_sets": sets})
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

