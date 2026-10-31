"""Layer-1 soft/quality rules (test-local data-quality pass), one small module.

Why here: the gate (A1) and the soft layer (A2/B1/B2/E2) must agree on what a
"restaurant" / "bar" is and where the meal slots are. This module owns those
primitives so `gate.py`, `validator.py`, `rank.py` and `scorer.py` all read
the same definitions.

Rules
-----
- A2 (soft, ACTIVE/canonical meal spacing): two `restaurant` POIs less than
  2.5h apart (START to START), regardless of meal-slot labels -> split meal.
  Pair penalty on the edge (folded into `scorer.edge_scores`) plus a
  plan-level issue; the optimizer also carries a pairwise A2 objective term
  (gate A1 only guards the hard slot boundary, so 10:49 vs 11:00 slips past
  it). A2 is the ONE owner of "two meals too close in time"; B1's same-type
  term is folded into the same restaurant edge, not a second rule.
- B1 (soft, DEPRECATED as an independent rule): the old "two consecutive
  same-type POIs" edge penalty. It is the soft mirror of the HARD
  NO_CONSECUTIVE rule, so NO_CONSECUTIVE is canonical; B1 survives only as
  the edge-weight term the optimizer reads (see `gate.RULE_FREEZE`).
- B2 (soft, DEPRECATED as an independent rule): "more than two same-type
  POIs in one day". The hard day-level caps own counting now: CATEGORY_CAP
  (non-food, cap 1) and CAFE_CAP (cafe, cap 2). B2 survives only as a
  report-only penalty for the types those caps deliberately exclude
  (`gate.RULE_FREEZE`).
- E2 (soft, ACTIVE): `bar`/`nightlife` starting before 17:00 -> rank time_fit
  penalty (a bar in the morning is a semantic absurdity, not a hard error).

Freeze note: rule status (active / deprecated + canonical owner + reason) is
declared once in `gate.RULE_FREEZE`; this module never deletes a rule on its
own, it only marks the deprecated ones here and keeps their numbers stable so
scoring/ranking does not shift.

HARD sequence rules (they live in `gate.py`, the primitives here):
- CAFE_CAP: one cafe per day by default. A second cafe is allowed only when
  the two sit in DIFFERENT dayparts (morning start < 11:00 AND afternoon
  start > 13:00) AND the profile shows a cafe need (food_prefs/activities
  mention cafe/coffee, or pace == 3). More than two cafes is always HARD.
  `cafe_need`/`cafe_cap`/`cafe_daypart` are the single definition used by
  the gate AND the optimizer, so the solver avoids the cap instead of
  producing a plan the gate then rejects.
- CATEGORY_CAP: at most ONE non-food POI per category per day
  (`NON_FOOD_CAPPED`: market/landmark/beach/attraction/temple/museum/park/
  viewpoint). Two markets or two beaches in one day is a broken plan. Meals
  are exempt (A1 + CAFE_CAP own them). `is_capped_category` /
  `category_allowed` are the shared primitives: the gate check, the
  optimizer constraint and the greedy seed all read them.
- NO_CONSECUTIVE (canonical): two back-to-back POIs of the same category are
  HARD. No exemptions (the old B1 cafe->cafe morning exemption only survives
  as a soft edge penalty; adjacency is now a broken plan, not a taste choice).
  `same_category_edges` is the ONE adjacency scan: the gate check, the
  validator offender list and B1 all read it.
- NO_ADJACENT_FOOD (deprecated, subsumed by NO_CONSECUTIVE): "no two
  consecutive `restaurant` POIs, whatever the cuisine". It is a strict subset
  of NO_CONSECUTIVE (both read `poi_category`), so it stays in the registry
  as a naming/compat layer computed by `same_category_edges(..., only=
  "restaurant")`, not as a second predicate.
- REST_FOLLOWS_LUNCH: the siesta window START is the lunch restaurant's END
  time (no fixed 13:00 anchor). Length by pace (60/45/30 min); a late lunch
  (> 15:00) shrinks it to fit the day, never below REST_MIN_FLOOR (20 min).
  `rest_span`/`lunch_activity`/`rest_minutes` are the single definition used
  by gate, validator, optimizer (via templates) and the plan report.

A1 (HARD: at most one restaurant per meal slot) lives in `gate.py`; it uses
`MEAL_SLOTS`/`meal_slot`/`poi_category` from here.
F1 (SOFT: every day needs >=1 food AND >=1 culture/nature/sightseeing POI)
also lives in `gate.py`, but is listed under `SOFT_CHECKS` so it only
reports a violation/penalty and never fail-closes a plan. The category
sets below are the single definition used by gate/validator/repair.

Edge penalties (A2/B1) are small on purpose: they only nudge the optimizer's
transition choice (q_ij), they never outweigh a POI's own score.
B2/E2 are sequence-level; the CP-SAT objective has no day-level count term,
so they are reported on the plan (`soft_penalties`) for review/ranking.
"""

from __future__ import annotations

from collections import Counter

from BE.app.services.profile_filter import fold, has_word
from BE.common import to_min

# Meal slots (minutes since midnight): lunch 11:00-14:00, dinner 17:00-21:00.
MEAL_SLOTS = ((11 * 60, 14 * 60), (17 * 60, 21 * 60))

# PAPER MEAL WINDOWS (dynamic state, trip_ctx): the rhythm the planner scores
# against. Distinct from MEAL_SLOTS above, which is the HARD gate's slot
# membership (at most one restaurant per slot). Breakfast 07-09, lunch
# 11:30-13:30, snacks ~10:00 / 15:00-16:30, dinner 18:00-20:00.
MEAL_WINDOWS = (
    {"name": "breakfast", "start": 7 * 60, "end": 9 * 60, "heavy": False},
    {"name": "snack_morning", "start": 10 * 60, "end": 10 * 60 + 30,
     "heavy": False, "snack": True},
    {"name": "lunch", "start": 11 * 60 + 30, "end": 13 * 60 + 30,
     "heavy": True},
    {"name": "snack_afternoon", "start": 15 * 60, "end": 16 * 60 + 30,
     "heavy": False, "snack": True},
    {"name": "dinner", "start": 18 * 60, "end": 20 * 60, "heavy": True},
)
# A window is "present" only when the trip can actually hold 60 minutes of
# it: a morning half-day gets no lunch (and no forced restaurant rhythm),
# while a 07:00-13:00 day still eats lunch at 11:30.
MIN_MEAL_OVERLAP = 60

# Universal lunch + rest (HUMAN NEED, every template/archetype/custom profile):
# the lunch restaurant must start inside LUNCH_REQUIRED (11:00-13:00). The
# siesta follows lunch: it STARTS at the lunch activity's end time (there is
# no fixed 13:00 anchor any more). REST_MIN_BY_PACE is the requested length;
# a late lunch (> REST_LATE_LUNCH) shrinks it to fit the day, floor
# REST_MIN_FLOOR. The dinner slot holds at most one restaurant (gate A1).
LUNCH_SLOT = MEAL_SLOTS[0]                 # 11:00-14:00
LUNCH_REQUIRED = (LUNCH_SLOT[0], 13 * 60)  # restaurant start must be < 13:00
REST_MIN_BY_PACE = {1: 60, 2: 45, 3: 30}   # pace 3 -> 30-minute power nap
REST_DEFAULT_MIN = 45
REST_MIN_FLOOR = 20                        # never shrink below this
REST_LATE_LUNCH = 15 * 60                  # lunch ending after 15:00 -> shrink
REST_START_TOLERANCE = 15                  # gate: rest may start <=15 min late
# Dinner: a restaurant starting in this window, on a day that covers the meal.
# The start window is wider than the paper one so a 20:00 end still fits a dinner.
DINNER_REQUIRED = (17 * 60 + 30, 20 * 60 + 30)
DINNER_MIN_END = 19 * 60 + 30              # a day ending earlier has no room for it
DINNER_LATEST_START = 18 * 60              # ... and one starting later already ate


# F1 (soft category quota): a day needs at least one food stop and at least
# one culture/nature/sightseeing stop. Categories are the canonical English
# ones from `poi_category` (snapshot `cat`, legacy `type` fallback).
# `bar`/`spa`/`lodging`/`transport` are neither: they cannot satisfy variety.
FOOD_CATEGORIES = frozenset({"restaurant", "cafe"})
SIGHTSEEING_CATEGORIES = frozenset({
    "attraction", "landmark", "museum", "park", "temple",
    "beach", "viewpoint", "nature",
})

SAME_TYPE_PENALTY = 0.3         # B1, edge-score units
RESTAURANT_PAIR_PENALTY = 0.45  # A2
RESTAURANT_PAIR_MAX_GAP = 150   # A2: under 2.5 hours
EXEMPT_SAME_TYPE = frozenset({("cafe", "cafe"), ("viewpoint", "sunset_view")})
TYPE_LIMIT = 2                  # B2: more than this per day is penalized
TYPE_PENALTY_STEP = 0.5         # B2: grows with each extra occurrence
NIGHT_TYPES = frozenset({"bar", "nightlife"})
NIGHT_START = 17 * 60           # E2: nightlife before 17:00 is a mismatch
NIGHT_PENALTY = 0.3             # E2 (rank/plan units)
# State-aware food transition (soft, only when a trip context is passed):
# still full after the meal anchor -> don't stack another meal.
EDGE_FOOD_FULL_PENALTY = 0.2
EDGE_FOOD_FULL_CAFE_PENALTY = 0.05
EDGE_FOOD_HUNGRY_BONUS = 0.05

# --- universal per-category daily cap (HARD CATEGORY_CAP) ------------------
# One non-food POI per category per day. A second market/landmark/beach/...
# on the same day is a broken plan (two night markets, two beaches), not a
# taste choice. Meals are exempt: restaurant/cafe keep A1/CAFE_CAP.
# `bar`/`spa`/`lodging`/`transport` are deliberately NOT capped here (they are
# not "sights" and the profile/archetype bans already govern them).
NON_FOOD_CAPPED = frozenset({
    "market", "shop", "landmark", "beach", "attraction", "temple", "museum", "park",
    "viewpoint",
})
CATEGORY_DAILY_CAP = 1          # >1 of a capped category in one day = HARD

# --- universal cafe quota (HARD CAFE_CAP) ----------------------------------
CAFE_DEFAULT_CAP = 1            # one cafe per day unless the profile allows 2
CAFE_MAX_CAP = 2                # never more than two, whatever the profile
CAFE_MORNING_END = 11 * 60      # morning daypart: start before 11:00
CAFE_AFTERNOON_START = 13 * 60  # afternoon daypart: start after 13:00
CAFE_FAST_PACE = 3              # pace 3 (fast day) counts as a cafe need
# Folded needles (profile_filter.fold strips diacritics: "cà phê" -> "ca phe").
CAFE_NEED_WORDS = ("cafe", "coffee", "ca phe", "caphe")


def poi_category(poi: dict | None) -> str:
    """Canonical English category (`cat`), falling back to `type`.

    The snapshot stores the English category in `cat` and a Vietnamese label
    in `type`; older fixtures only carry `type` ("restaurant", "cafe", ...).
    """
    poi = poi or {}
    return str(poi.get("cat") or poi.get("type") or "").strip().lower()


def is_capped_category(category: str) -> bool:
    """Is this category under the HARD one-per-day cap (CATEGORY_CAP)?"""
    return str(category or "").strip().lower() in NON_FOOD_CAPPED


def category_allowed(category: str, used: dict[str, int] | None,
                     cap: int = CATEGORY_DAILY_CAP) -> bool:
    """Mirror of CATEGORY_CAP for seed/greedy builders: may we add one more?

    Meals (restaurant/cafe) are exempt and always allowed here; their quotas
    are A1/CAFE_CAP. A missing category is never capped.
    """
    cat = str(category or "").strip().lower()
    if not is_capped_category(cat):
        return True
    return int((used or {}).get(cat, 0)) < int(cap)


def meal_slot(start: str) -> int | None:
    """Index of the meal slot containing `start`, or None outside slots."""
    minutes = to_min(start)
    for idx, (lo, hi) in enumerate(MEAL_SLOTS):
        if lo <= minutes < hi:
            return idx
    return None


def meal_slots(trip: dict | None) -> list[dict]:
    """Paper meal windows the trip can hold (>= MIN_MEAL_OVERLAP minutes).

    CONDITIONAL by design: no forced lunch on a morning half-day, no dinner
    on a day that ends before 19:00 (see trip_ctx for the state that uses it).
    """
    trip = trip or {}
    start = to_min(trip.get("start_time") or "07:00")
    end = to_min(trip.get("end_time") or "18:00")
    out = []
    for window in MEAL_WINDOWS:
        lo, hi = max(start, window["start"]), min(end, window["end"])
        need = min(MIN_MEAL_OVERLAP, window["end"] - window["start"])
        if hi - lo >= need:
            out.append({**window, "overlap": hi - lo})
    return out


def meal_window_present(trip: dict | None, name: str) -> bool:
    """True when the trip covers enough of that meal window."""
    return any(s["name"] == name for s in meal_slots(trip))


def covers_dinner(trip: dict | None) -> bool:
    """Does this day run through dinner? A meal must be possible inside it."""
    trip = trip or {}
    return (to_min(trip.get("end_time") or "18:00") >= DINNER_MIN_END
            and to_min(trip.get("start_time") or "07:00") <= DINNER_LATEST_START)


# --- when a stop makes sense (TIME_FIT) ------------------------------------
# On top of when a place is OPEN: a restaurant at 16:00, a beach in the midday
# sun, a pagoda at 20:00 are open and still wrong. Each entry lists the windows a
# whole visit must fit inside, on the same clock as `open_windows`.
_EVENING = 26 * 60
_ALL_DAY = ((5 * 60, _EVENING),)
_MEALS = ((10 * 60 + 30, 15 * 60), (17 * 60, 22 * 60 + 30))
_EATERY = ((6 * 60 + 30, 15 * 60), (17 * 60, 22 * 60 + 30))
_DAYLIGHT = ((5 * 60, 18 * 60 + 15),)
_NOT_MIDDAY = ((5 * 60, 11 * 60 + 30), (14 * 60 + 30, 21 * 60))
TIME_FIT_BY_CAT = {
    "restaurant": _MEALS,
    "bar": ((16 * 60 + 30, _EVENING),),
    "beach": ((5 * 60, 11 * 60 + 30), (15 * 60, 18 * 60 + 30)),
    "viewpoint": _DAYLIGHT,
    "nature": ((5 * 60 + 30, 18 * 60),),
    "park": _NOT_MIDDAY,
    "temple": ((5 * 60, 18 * 60),),
    "market": ((5 * 60, 11 * 60 + 30), (14 * 60, 22 * 60)),
    "landmark": ((6 * 60, 22 * 60 + 30),),
}
TIME_FIT_BY_SUBCAT = {
    "eatery": _EATERY,
    "sunrise": ((5 * 60, 9 * 60 + 30),),
    "sunset": ((15 * 60, 19 * 60),),
    "night_market": ((17 * 60, _EVENING),),
    "church": ((5 * 60, 18 * 60),),
}


def time_fit_windows(poi: dict | None) -> tuple | None:
    """Windows a visit must fit, None = any time it is open.

    Only a POI of the reviewed snapshot carries a rule (`plan_tier` marks it): a
    plain `cat` on a test fixture or a fresh crawl says too little to forbid an hour.
    """
    poi = poi or {}
    if "plan_tier" not in poi:
        return None
    return TIME_FIT_BY_SUBCAT.get(poi.get("subcat")) or TIME_FIT_BY_CAT.get(poi_category(poi))


def fits_time_of_day(poi: dict | None, start: int, end: int) -> bool:
    """Gate TIME_FIT: does this visit lie inside the POI's sensible hours?"""
    windows = time_fit_windows(poi)
    return windows is None or any(lo <= start and end <= hi for lo, hi in windows)


def clip_to_time_fit(poi: dict | None, windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Opening windows cut down to the sensible hours; [] = no sensible time today."""
    fit = time_fit_windows(poi)
    if fit is None:
        return windows
    return [(max(a, lo), min(b, hi)) for a, b in windows for lo, hi in fit
            if max(a, lo) < min(b, hi)]


def is_food(poi: dict | None) -> bool:
    """F1: a food stop is a restaurant/cafe (meal-bearing categories)."""
    return poi_category(poi) in FOOD_CATEGORIES


def is_sightseeing(poi: dict | None) -> bool:
    """F1: culture/nature/sightseeing categories (the non-food half)."""
    return poi_category(poi) in SIGHTSEEING_CATEGORIES


def in_nightlife_type(poi: dict | None) -> bool:
    return poi_category(poi) in NIGHT_TYPES


def cafe_daypart(start: str) -> str | None:
    """CAFE_CAP daypart of a cafe start: "morning" (<11:00) / "afternoon"
    (>13:00), else None (the 11:00-13:00 window is not a valid 2nd-cafe slot).

    Keyed by activity START, like the meal slots (gate A1).
    """
    minutes = to_min(start)
    if minutes < CAFE_MORNING_END:
        return "morning"
    if minutes > CAFE_AFTERNOON_START:
        return "afternoon"
    return None


def _pace(profile: dict) -> int:
    try:
        pace = int((profile or {}).get("pace") or 2)
    except (TypeError, ValueError):
        return 2
    return min(3, max(1, pace))


def cafe_need(profile: dict | None) -> bool:
    """Does the profile ask for cafe/coffee time (or a pace-3 fast day)?

    Only the onboarding preferences count (food_prefs / activities); a plan
    must not grant itself a second cafe from POI names.
    """
    profile = profile or {}
    if _pace(profile) >= CAFE_FAST_PACE:
        return True
    prefs = list(profile.get("food_prefs") or []) + list(
        profile.get("activities") or [])
    text = fold(" ".join(str(item) for item in prefs))
    return has_word(text, CAFE_NEED_WORDS)


def cafe_cap(profile: dict | None) -> int:
    """HARD cafe cap for one day: CAFE_MAX_CAP with a cafe need, else 1."""
    return CAFE_MAX_CAP if cafe_need(profile) else CAFE_DEFAULT_CAP


def is_restaurant(poi: dict | None) -> bool:
    """NO_ADJACENT_FOOD / A1 view: any restaurant, whatever its cuisine."""
    return poi_category(poi) == "restaurant"


def same_category_edges(activities: list[dict] | None, pois: dict,
                        only: str | None = None) -> list[tuple[dict, dict]]:
    """Canonical "back-to-back POIs of the same category" scan.

    ONE implementation for NO_CONSECUTIVE (hard), its deprecated subset
    NO_ADJACENT_FOOD (`only="restaurant"`) and the soft B1 edge penalty, so a
    future change to what "adjacent" means cannot drift between them.

    `activities` are taken in START order (the caller passes them unordered);
    a missing category is never "the same". `only` narrows the scan to one
    category without changing the definition of adjacency.
    Returns the offending (left, right) activity pairs.
    """
    acts = sorted(activities or [], key=lambda a: a.get("start", ""))
    out: list[tuple[dict, dict]] = []
    for x, y in zip(acts, acts[1:]):
        left = poi_category(pois.get(x.get("poi_id")))
        right = poi_category(pois.get(y.get("poi_id")))
        if not left or left != right:
            continue
        if only is not None and left != only:
            continue
        out.append((x, y))
    return out


def lunch_activity(activities: list[dict], pois: dict) -> dict | None:
    """The universal lunch: the restaurant STARTing inside 11:00-13:00.

    Gate A1 caps the slot at one, so the first hit is the lunch. Returns the
    activity dict (not the POI) because the rest window is tied to its END.
    """
    for act in sorted(activities or [], key=lambda a: a.get("start", "")):
        if not is_restaurant(pois.get(act.get("poi_id"))):
            continue
        minutes = to_min(act.get("start"))
        if LUNCH_REQUIRED[0] <= minutes < LUNCH_REQUIRED[1]:
            return act
    return None


def rest_minutes(profile: dict | None, lunch_end: int | None = None,
                 deadline: int | None = None) -> int:
    """Siesta length by pace; shrunk to fit a late lunch (never < floor).

    Normal plan: 60/45/30 min for pace 1/2/3. When lunch ends after
    REST_LATE_LUNCH (15:00) the window is clipped to the remaining day
    (`deadline - lunch_end`) so the plan is not forced past its horizon,
    with REST_MIN_FLOOR as the hard floor. The shrink is reported by callers.
    """
    pace = _pace(profile)
    length = REST_MIN_BY_PACE[pace]
    if lunch_end is not None and lunch_end > REST_LATE_LUNCH:
        if deadline is None:
            length = max(REST_MIN_FLOOR, length - (lunch_end - REST_LATE_LUNCH))
        else:
            length = max(REST_MIN_FLOOR, min(length, deadline - lunch_end))
    return int(length)


def rest_span(activities: list[dict], pois: dict, profile: dict | None,
              deadline: int | None = None) -> dict | None:
    """Siesta window tied to lunch end, or None when there is no lunch.

    {"start", "end", "minutes", "requested_minutes", "shrunk", "lunch_end",
    "lunch_poi_id"}. `start` is exactly the lunch activity end (that is the
    rule); `shrunk` is True when REST_MIN_BY_PACE had to give way.
    """
    lunch = lunch_activity(activities, pois)
    if lunch is None:
        return None
    lunch_end = to_min(lunch.get("end"))
    requested = REST_MIN_BY_PACE[_pace(profile)]
    minutes = rest_minutes(profile, lunch_end, deadline)
    return {
        "start": lunch_end,
        "end": lunch_end + minutes,
        "minutes": minutes,
        "requested_minutes": requested,
        "shrunk": minutes < requested,
        "lunch_end": lunch_end,
        "lunch_poi_id": lunch.get("poi_id"),
    }


def effective_rest(span: dict | None, declared: dict | None) -> dict | None:
    """Apply a plan's declared rest window ({"start","end"}) over the derived
    span, if it has one. The gate/report can then verify the window the plan
    actually claims (within tolerance), not just the one we would infer."""
    if not span:
        return None
    rest = declared or {}
    start = to_min(rest["start"]) if rest.get("start") else span["start"]
    end = to_min(rest["end"]) if rest.get("end") else start + span["minutes"]
    return {**span, "start": start, "end": end, "minutes": end - start}




def edge_penalty(a: dict | None, b: dict | None,
                 ctx: dict | None = None) -> float:
    """A2 + B1 pair penalty (<= 0) for the transition a -> b.

    State extension (soft): when the caller passes the trip context, a food
    transition is judged against the post-lunch satiety anchor
    (`trip_ctx.edge_state`, 14:30 by default): still full -> an extra penalty
    on entering a restaurant (a cafe only slightly), hungry -> a small bonus
    for a meal. Legacy callers (no ctx) get the exact previous numbers.
    """
    ca, cb = poi_category(a), poi_category(b)
    penalty = 0.0
    if ca and ca == cb and (ca, cb) not in EXEMPT_SAME_TYPE:
        penalty = -SAME_TYPE_PENALTY
        if ca == "restaurant":
            # A2 owns meal spacing; the deprecated B1 same-type term is folded
            # into this ONE restaurant-edge weight (one rule, one number).
            penalty -= RESTAURANT_PAIR_PENALTY
    state = (ctx or {}).get("edge_state") or {}
    if state:
        satiety = float(state.get("satiety") or 0.0)
        if cb == "restaurant":
            if satiety > 0.6:
                penalty -= EDGE_FOOD_FULL_PENALTY
            elif satiety < 0.3:
                penalty += EDGE_FOOD_HUNGRY_BONUS
        elif cb in FOOD_CATEGORIES and satiety > 0.6:
            penalty -= EDGE_FOOD_FULL_CAFE_PENALTY
    return round(penalty, 3)



def plan_penalties(activities: list[dict], pois: dict,
                   trip: dict | None = None) -> dict:
    """Sequence-level soft report: {"penalty": float, "issues": [...]}.

    Each issue is {"rule", "poi_ids", "detail"} so the harness / review layer
    can show WHY a plan is not sensible, not just a number.
    """
    acts = sorted(activities or [], key=lambda a: a.get("start", ""))
    cats = [poi_category(pois.get(a.get("poi_id"))) for a in acts]
    issues: list[dict] = []
    penalty = 0.0

    # A2: restaurants closer than 2.5h (START to START), any slot labels.
    previous = None
    for act, cat in zip(acts, cats):
        if cat != "restaurant":
            continue
        if previous is not None:
            gap = to_min(act["start"]) - to_min(previous["start"])
            if gap < RESTAURANT_PAIR_MAX_GAP:
                penalty += RESTAURANT_PAIR_PENALTY
                issues.append({
                    "rule": "A2",
                    "poi_ids": [previous["poi_id"], act["poi_id"]],
                    "detail": f"2 nha hang cach nhau {gap} phut",
                })
        previous = act

    # B1 (DEPRECATED as an independent rule; the soft mirror of the HARD
    # NO_CONSECUTIVE): consecutive same type, exempt pairs skipped. It reads
    # the same adjacency scan as the gate so the two can never disagree.
    for x, y in same_category_edges(acts, pois):
        pair = (poi_category(pois.get(x.get("poi_id"))),
                poi_category(pois.get(y.get("poi_id"))))
        if pair in EXEMPT_SAME_TYPE:
            continue
        penalty += SAME_TYPE_PENALTY
        issues.append({
            "rule": "B1",
            "poi_ids": [x["poi_id"], y["poi_id"]],
            "detail": f"2 diem cung loai '{pair[0]}' lien tiep",
        })

    # B2 (DEPRECATED as an independent rule): CATEGORY_CAP/CAFE_CAP own the
    # day-level caps; this survives only as a report-only penalty for the
    # types they exclude.
    for cat, count in Counter(c for c in cats if c).items():
        if count > TYPE_LIMIT:
            extra = count - TYPE_LIMIT
            penalty += TYPE_PENALTY_STEP * extra * (extra + 1) / 2
            issues.append({
                "rule": "B2",
                "poi_ids": [a["poi_id"] for a, c in zip(acts, cats) if c == cat],
                "detail": f"{count} diem cung loai '{cat}' trong 1 ngay",
            })

    # E2: nightlife before 17:00.
    for act, cat in zip(acts, cats):
        if cat in NIGHT_TYPES and to_min(act["start"]) < NIGHT_START:
            penalty += NIGHT_PENALTY
            issues.append({
                "rule": "E2",
                "poi_ids": [act["poi_id"]],
                "detail": f"'{cat}' bat dau {act['start']} (truoc 17:00)",
            })

    return {"penalty": round(penalty, 3), "issues": issues}
