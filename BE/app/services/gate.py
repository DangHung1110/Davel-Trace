"""Canonical gate registry (T011 + T061f), shared by validator + evaluator.

ONE registry for the gate checks (fixes X8 "2 bộ cổng"): gate.py owns the
formulas, `BE/eval/metrics.py` imports `CHECKS` and reads their `score`.
Every check returns the canonical shape ``{"passed": bool, "score": float}``
with a finite score in [0, 1]:
- FAR: no activity on unknown/unverified POI (FR-013); score = verified
  ratio.
- PROFILE_SAFE: no activity violates the onboarding profile's hard filter
  (allergy / must_avoid / accessibility, `profile_filter.drop_reason`). The
  router drops those POIs before planning; this re-checks the final plan so a
  planner path that skips the pre-filter can never ship an allergen.
  No profile filter -> passes vacuously. score = safe activity ratio.
- VROH: no activity outside POI opening hours (SC-006); score = compliant
  ratio.
- B3: no broken transit buffer — every consecutive transition's gap fits
  the matrix travel minutes (R4/B3: a missing cell is infeasible, never
  0/haversine); score = compliant transition ratio.
- BCS: total cost within budget (SC-008).
- ETB: the last activity ends by the deadline = min(end_time, return_time);
  `return_time` is a HARD within-day cap, never silently stretched to
  end_time (an evening extension must be a new, re-gated plan).
- A1: at most one `restaurant` POI per meal slot (lunch 11:00-14:00,
  dinner 17:00-21:00), by activity start time. Two lunches is not a
  preference, it is a broken plan (data-quality pass, test-local).
- CAFE_CAP: one `cafe` per day by default. A second cafe passes only when
  the two are in different dayparts (morning start < 11:00 and afternoon
  start > 13:00) AND the profile shows a cafe need (food_prefs/activities
  mention cafe/coffee, or pace == 3). More than two cafes is always HARD.
  score = allowed cafes / actual cafes.
- CATEGORY_CAP: at most ONE non-food POI per category per day (market,
  landmark, beach, attraction, temple, museum, park, viewpoint). A second one
  is a HARD violation, no profile exemption; meals keep A1/CAFE_CAP.
  score = allowed capped visits / actual capped visits.
- NO_CONSECUTIVE: no two back-to-back POIs of the same category. No
  exemptions: cafe->cafe is a broken plan now (it stays only as the SOFT
  B1 edge penalty). This is the CANONICAL adjacency rule; the scan lives in
  `soft_rules.same_category_edges`. score = compliant transition ratio.
- NO_ADJACENT_FOOD (DEPRECATED, subsumed by NO_CONSECUTIVE): no two
  back-to-back `restaurant` POIs, ANY cuisine (BBQ->vegan included). A strict
  subset of NO_CONSECUTIVE (both read `poi_category`), kept in the registry
  for named reporting/compat and computed by the SAME scan with
  `only="restaurant"` — never a second predicate. See `RULE_FREEZE`.
  score = compliant transition ratio.
- REST_FOLLOWS_LUNCH: the siesta starts at the lunch restaurant's end
  (lunch = restaurant starting 11:00-13:00), length by pace (60/45/30),
  shrunk for a late lunch (floor 20 min) and with no other POI inside.
  Legacy plans (no onboarding profile) pass vacuously.
  score = compliant activity ratio.
- F1 (SOFT): every day needs at least one food POI (`restaurant`/`cafe`)
  AND at least one culture/nature/sightseeing POI (`attraction`,
  `landmark`, `museum`, `park`, `beach`, `viewpoint`, `nature`). A plan
  that is all food is semantically poor, not infeasible: F1 is in the
  registry but listed in `SOFT_CHECKS`, so it reports a violation/penalty
  and never fail-closes (score = satisfied halves / 2).
- TCS: time mirror — VROH/B3/ETB all pass AND no overlap AND every
  activity fits [start_time, deadline].
- HCS: hard mirror — the concrete gates (incl. PROFILE_SAFE, A1, CAFE_CAP,
  CATEGORY_CAP, NO_CONSECUTIVE, NO_ADJACENT_FOOD, REST_FOLLOWS_LUNCH) pass AND must_visit
  present AND avoid absent. Soft checks (F1) are NOT mirrored. The deprecated
  NO_ADJACENT_FOOD stays in the mirror only as the compat view of
  NO_CONSECUTIVE (see `RULE_FREEZE`); it adds no constraint of its own.

Inputs are the shared plain dicts (itinerary/trip/pois/matrix) used by the
validator (T049) and the tier-1 evaluator.

RULE_FREEZE (below) is the single audit surface for "which rule owns what":
one canonical rule per group, the duplicates kept in code but marked
deprecated with a reason and their canonical owner. Nothing is deleted and no
pass/fail semantics change: a deprecated rule that still executes is computed
from the canonical implementation, so it can never disagree with it.
"""

from __future__ import annotations

import functools

from BE.app.services.soft_rules import (
    CAFE_DEFAULT_CAP,
    CAFE_MAX_CAP,
    CATEGORY_DAILY_CAP,
    MEAL_SLOTS,
    NON_FOOD_CAPPED,
    REST_START_TOLERANCE,
    cafe_daypart,
    cafe_need,
    effective_rest,
    is_food,
    is_sightseeing,
    lunch_activity,
    meal_slot,
    meal_window_present,
    poi_category,
    rest_span,
    same_category_edges,
)
from BE.app.services.profile_filter import drop_reason
from BE.common import deadline, in_range, party_size, plan_cost, to_min

EPS = 1e-9


def _result(passed: bool, score: float | None = None) -> dict:
    """Canonical gate result: passed is a real bool, score a finite float."""
    passed = bool(passed)
    if score is None:
        score = 1.0 if passed else 0.0
    score = max(0.0, min(1.0, float(score)))
    return {"passed": passed, "score": score}


def _ordered(itinerary: dict) -> list[dict]:
    return sorted(itinerary.get("activities", []), key=lambda a: a["start"])


def split_days(itinerary: dict) -> list[dict]:
    """One itinerary per `day` (multiday.py); a one-day plan is returned as it is."""
    days: dict = {}
    for act in itinerary.get("activities", []):
        days.setdefault(act.get("day"), []).append(act)
    if len(days) <= 1:
        return [itinerary]
    return [{**itinerary, "activities": days[day]} for day in sorted(days, key=lambda d: d or 0)]


def _per_day(check):
    """A rule of one day: on a longer trip every day must pass it on its own
    (clock times repeat across days, and each day has its own caps and lunch)."""
    @functools.wraps(check)
    def wrapped(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
        results = [check(day, trip, pois, matrix) for day in split_days(itinerary)]
        return _result(all(r["passed"] for r in results), min(r["score"] for r in results))
    return wrapped


def check_far(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Pass iff every activity uses a verified POI (non-empty plan)."""
    acts = itinerary.get("activities", [])
    if not acts:
        return _result(False, 0.0)
    bad = sum(1 for a in acts
              if a.get("poi_id") not in pois
              or not (pois.get(a["poi_id"]) or {}).get("verified"))
    return _result(bad == 0, 1.0 - bad / len(acts))


def check_profile_safe(itinerary: dict, trip: dict, pois: dict,
                       matrix: dict) -> dict:
    """Pass iff no activity hits the profile's allergy/must_avoid/access rule."""
    profile = trip.get("profile") or {}
    acts = itinerary.get("activities", [])
    if not acts or not any(profile.get(k) for k in
                           ("allergy", "must_avoid", "accessibility")):
        return _result(True, 1.0)
    bad = sum(1 for a in acts
              if drop_reason(pois.get(a.get("poi_id")) or {}, profile))
    return _result(bad == 0, 1.0 - bad / len(acts))


def check_vroh(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Pass iff every activity fits opening hours; score = compliant ratio."""
    acts = itinerary.get("activities", [])
    if not acts:
        return _result(True, 1.0)
    bad = 0
    for a in acts:
        hours = (pois.get(a.get("poi_id"), {}) or {}).get("opening_hours") or []
        s, e = to_min(a["start"]), to_min(a["end"])
        if hours and not any(in_range(s, e, h) for h in hours):
            bad += 1
    return _result(bad == 0, 1.0 - bad / len(acts))


@_per_day
def check_b3(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Pass iff each gap fits matrix travel time; score = compliant ratio."""
    acts = _ordered(itinerary)
    if len(acts) < 2:
        return _result(True, 1.0)
    bad = 0
    for x, y in zip(acts, acts[1:]):
        gap = to_min(y["start"]) - to_min(x["end"])
        need = (matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {}).get("minutes")
        if need is None or gap < need:
            bad += 1
    return _result(bad == 0, 1.0 - bad / (len(acts) - 1))


def check_bcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Pass iff total cost is within budget (one formula, both sides)."""
    cost = plan_cost(itinerary, pois, party_size(trip))
    return _result(cost <= int(trip.get("budget", 0)))


def check_etb(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """`return_time` is a hard within-day deadline; min(end_time, return_time)."""
    acts = itinerary.get("activities", [])
    if not acts or not (trip.get("end_time") or trip.get("return_time")):
        return _result(True)
    last_end = max(to_min(a["end"]) for a in acts)
    return _result(last_end <= deadline(trip))


@_per_day
def check_a1(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Pass iff at most one restaurant sits inside each meal slot.

    Meal slots are keyed by activity START time (lunch 11:00-14:00, dinner
    17:00-21:00). Only the `restaurant` category counts — cafes, dessert
    shops and markets do not. score = compliant restaurant ratio.
    """
    counts = [0] * len(MEAL_SLOTS)
    for a in itinerary.get("activities", []):
        if poi_category(pois.get(a.get("poi_id"), {})) != "restaurant":
            continue
        slot = meal_slot(a["start"])
        if slot is not None:
            counts[slot] += 1
    total = sum(counts)
    over = sum(count - 1 for count in counts if count > 1)
    return _result(over == 0, 1.0 - over / total if total else 1.0)


@_per_day
def check_cafe_cap(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """HARD cafe quota: 1/day; 2 only split across dayparts with a cafe need.

    Dayparts are keyed by activity START (morning < 11:00, afternoon > 13:00),
    exactly like `cafe_daypart` mirrors in the optimizer. A profile without a
    cafe need (no cafe/coffee in food_prefs/activities, pace < 3) allows one
    cafe; a third cafe is always a violation. score = allowed / actual.
    """
    cafes = [a for a in _ordered(itinerary)
             if poi_category(pois.get(a.get("poi_id")) or {}) == "cafe"]
    count = len(cafes)
    if count <= CAFE_DEFAULT_CAP:
        return _result(True, 1.0)
    split = {cafe_daypart(a["start"]) for a in cafes}
    two_ok = (count == CAFE_MAX_CAP
              and cafe_need(trip.get("profile") or {})
              and split == {"morning", "afternoon"})
    if two_ok:
        return _result(True, 1.0)
    return _result(False, min(1.0, CAFE_DEFAULT_CAP / count))


@_per_day
def check_category_cap(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """HARD daily category cap: at most ONE non-food POI per category.

    Two markets / landmarks / beaches / attractions / temples / museums /
    parks / viewpoints in the same day is a broken plan (the traveler does not
    need two night markets), not a taste choice. The profile makes no
    difference: the cap is universal and HARD, and the optimizer mirrors it
    (`category_cap`) so the solver never produces a plan this check rejects.

    Meals are exempt: `restaurant` keeps gate A1 (one per meal slot) and
    `cafe` keeps CAFE_CAP (1/day, 2 across dayparts with a cafe need).
    Categories are read through `poi_category`, so a legacy fixture without a
    category is never counted. score = allowed / actual over capped visits.
    """
    counts: dict[str, int] = {}
    for a in itinerary.get("activities", []):
        cat = poi_category(pois.get(a.get("poi_id")) or {})
        if cat in NON_FOOD_CAPPED:
            counts[cat] = counts.get(cat, 0) + 1
    total = sum(counts.values())
    if not total:
        return _result(True, 1.0)
    over = sum(count - CATEGORY_DAILY_CAP for count in counts.values()
               if count > CATEGORY_DAILY_CAP)
    return _result(over == 0, 1.0 - over / total)


@_per_day
def check_no_consecutive(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """CANONICAL adjacency rule: no two back-to-back POIs of the same category.

    The categories come from `poi_category` (snapshot `cat`, legacy `type`),
    so a missing category is ignored rather than treated as "same". The scan
    itself is `soft_rules.same_category_edges`, shared with the validator
    offender list, NO_ADJACENT_FOOD (its deprecated restaurant-only view) and
    the soft B1 penalty. score = compliant transition ratio.
    """
    acts = _ordered(itinerary)
    if len(acts) < 2:
        return _result(True, 1.0)
    bad = len(same_category_edges(acts, pois))
    return _result(bad == 0, 1.0 - bad / (len(acts) - 1))


@_per_day
def check_no_adjacent_food(itinerary: dict, trip: dict, pois: dict,
                           matrix: dict) -> dict:
    """DEPRECATED (kept for named reporting): adjacent restaurants.

    BBQ -> vegan is just as broken as two seafood places, but that is already
    NO_CONSECUTIVE: both rules read `poi_category`, so this is the same scan
    narrowed to `restaurant`. Kept in `CHECKS` so existing reports/API clients
    keep their name; `RULE_FREEZE` records it as deprecated with
    NO_CONSECUTIVE as the canonical owner. score = compliant edge ratio.
    """
    acts = _ordered(itinerary)
    if len(acts) < 2:
        return _result(True, 1.0)
    bad = len(same_category_edges(acts, pois, only="restaurant"))
    return _result(bad == 0, 1.0 - bad / (len(acts) - 1))


REST_NO_LUNCH = "khong co bua trua"
REST_BAD_WINDOW = "cua so nghi trua sai gio/do dai"


def rest_rule_violation(itinerary: dict, trip: dict,
                        pois: dict) -> tuple[str, list[str]] | None:
    """ONE definition of REST_FOLLOWS_LUNCH, shared by gate + validator.

    Returns None when the rule holds (or is vacuous: no onboarding profile,
    or a trip that cannot hold the lunch window at all), else
    ``(reason, offending_poi_ids)``:
    - ``REST_NO_LUNCH``: a lunch window exists but no restaurant starts in
      11:00-13:00;
    - ``REST_BAD_WINDOW``: the declared/derived siesta does not start at the
      lunch end (0..REST_START_TOLERANCE) or has the wrong length for the
      pace (a structural failure: the window itself is wrong);
    - ``""`` with ids: the window is structurally right but activities sit
      inside it.

    The validator's `details` and the gate's score are two views of this one
    function, so they cannot drift (a plan is never "failed with no reason").
    """
    profile = trip.get("profile") or {}
    if not profile:
        return None  # legacy plan without onboarding: no lunch/rest need
    if not meal_window_present(trip, "lunch"):
        # CONDITIONAL meals: a morning half-day (or a day that cannot hold
        # the 11:30-13:30 lunch window) has no lunch, so no siesta follows.
        return None
    acts = _ordered(itinerary)
    lunch = lunch_activity(acts, pois)
    if lunch is None:
        return (REST_NO_LUNCH, [])
    span = rest_span(acts, pois, profile, deadline(trip))
    if span is None:  # defensive: lunch_activity already proved a lunch
        return (REST_NO_LUNCH, [])
    declared = effective_rest(span, itinerary.get("rest"))
    lo, hi = declared["start"], declared["end"]
    late = lo - span["lunch_end"]
    structural = (0 <= late <= REST_START_TOLERANCE
                  and declared["minutes"] == span["minutes"])
    offenders = [a.get("poi_id") for a in acts
                 if a is not lunch
                 and to_min(a["start"]) < hi and to_min(a["end"]) > lo]
    if not structural:
        return (REST_BAD_WINDOW, offenders)
    if not offenders:
        return None
    return ("", offenders)


@_per_day
def check_rest_follows_lunch(itinerary: dict, trip: dict, pois: dict,
                             matrix: dict) -> dict:
    """HARD: the siesta exists and starts at the lunch restaurant's end.

    Rest is not an activity: it is inferred from the lunch activity, exactly
    like the report/optimizer do. The rule itself is
    `rest_rule_violation` (single definition, shared with the validator);
    this check only turns it into {passed, score}.
    - no profile / no lunch window -> vacuous pass (the gate never invents
      constraints);
    - missing lunch or a mis-timed/wrong-length siesta -> hard fail, score 0;
    - activities inside the siesta -> score = compliant activity ratio.
    """
    hit = rest_rule_violation(itinerary, trip, pois)
    if hit is None:
        return _result(True, 1.0)
    reason, offenders = hit
    if reason:  # structural: no lunch, or the siesta window itself is wrong
        return _result(False, 0.0)
    others = len(_ordered(itinerary)) - 1
    return _result(False, 1.0 - len(offenders) / others if others else 1.0)


@_per_day
def check_f1(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """SOFT category quota: >=1 food AND >=1 sightseeing per day.

    The optimizer/date model here is single-day (no per-activity date), so
    the whole activity list is one day. An empty plan is vacuously fine
    (FAR owns "non-empty"). score = met halves / 2, in [0, 1].
    """
    acts = itinerary.get("activities", [])
    if not acts:
        return _result(True, 1.0)
    cats = [pois.get(a.get("poi_id"), {}) for a in acts]
    has_food = any(is_food(p) for p in cats)
    has_sight = any(is_sightseeing(p) for p in cats)
    met = int(has_food) + int(has_sight)
    return _result(met == 2, met / 2.0)


@_per_day
def check_tcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Time mirror: VROH/B3/ETB + no overlap + inside [start, deadline]."""
    if not all(check(itinerary, trip, pois, matrix)["passed"]
               for check in (check_vroh, check_b3, check_etb)):
        return _result(False)
    acts = _ordered(itinerary)
    ws, we = to_min(trip.get("start_time", "07:00")), deadline(trip)
    for a in acts:
        s, e = to_min(a["start"]), to_min(a["end"])
        if s < ws or e > we or e <= s:
            return _result(False)
    for x, y in zip(acts, acts[1:]):
        if to_min(x["end"]) > to_min(y["start"]):
            return _result(False)
    return _result(True)


def check_hcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Hard mirror: concrete gates (incl. A1/CAFE_CAP/sequence/rest) + HCS."""
    if not all(check(itinerary, trip, pois, matrix)["passed"]
               for check in (check_far, check_profile_safe, check_vroh, check_b3,
                             check_bcs, check_etb, check_a1,
                             check_cafe_cap, check_category_cap,
                             check_no_consecutive,
                             check_no_adjacent_food, check_rest_follows_lunch)):
        return _result(False)
    ids = [a.get("poi_id") for a in itinerary.get("activities", [])]
    if any(m in ids for m in trip.get("avoid", [])) or len(ids) != len(set(ids)):
        return _result(False)
    # FR-020: a trip of N days is N days of stops, not one day and a promise.
    if len(split_days(itinerary)) < int(trip.get("days") or 1):
        return _result(False)
    must = trip.get("must_visit", [])
    if must and not all(m in ids for m in must):
        return _result(False)
    return _result(True)


CHECKS = (("FAR", check_far), ("PROFILE_SAFE", check_profile_safe),
          ("VROH", check_vroh),
          ("B3", check_b3), ("BCS", check_bcs), ("ETB", check_etb),
          ("A1", check_a1), ("CAFE_CAP", check_cafe_cap),
          ("CATEGORY_CAP", check_category_cap),
          ("NO_CONSECUTIVE", check_no_consecutive),
          ("NO_ADJACENT_FOOD", check_no_adjacent_food),
          ("REST_FOLLOWS_LUNCH", check_rest_follows_lunch),
          ("F1", check_f1), ("TCS", check_tcs), ("HCS", check_hcs))

# F1 is a quality quota, not feasibility: it is reported but never
# fail-closes a plan (SOFT severity, test-local). Everything else is hard.
SOFT_CHECKS = frozenset({"F1"})
HARD_CHECKS = tuple((name, fn) for name, fn in CHECKS
                    if name not in SOFT_CHECKS)


# --- RULE_FREEZE: one canonical rule per group, duplicates kept but marked ---
# Audit surface for Hướng 1 ("đóng băng rule"). Every rule that can fire
# anywhere (gate checks + soft_rules penalties) is listed once:
#   status    "active"     -> the canonical owner of its group
#             "deprecated" -> still in the code and still executed (so no
#                             report/API key disappears and the numbers do not
#                             move), but it is NO LONGER an independent rule:
#                             its implementation is the canonical one, narrowed.
#   family    the duplicate group it belongs to (rules in one family must not
#             grow a second independent definition).
#   canonical the rule that owns the family (None for a canonical rule).
#   reason    why the rule exists / why it was deprecated.
# Never delete an entry here without replacing it with a deprecation: a silent
# removal is exactly the drift this registry is meant to prevent.
RULE_FREEZE: dict[str, dict] = {
    # Hard safety gates: frozen as-is, no merge, no rename.
    "FAR": {
        "status": "active", "canonical": None, "family": "safety",
        "reason": "unknown/unverified POI is unsafe; hard safety gate, "
                  "kept untouched",
    },
    "PROFILE_SAFE": {
        "status": "active", "canonical": None, "family": "safety",
        "reason": "allergy/must_avoid/accessibility re-checked on the final "
                  "plan (defence in depth behind profile_filter.hard_filter)",
    },
    "VROH": {
        "status": "active", "canonical": None, "family": "hours",
        "reason": "opening hours / open-status safety; hard, kept untouched",
    },
    "ETB": {
        "status": "active", "canonical": None, "family": "time-window",
        "reason": "within-day deadline = min(end_time, return_time); hard, "
                  "kept untouched (return_time is never stretched)",
    },
    "BCS": {
        "status": "active", "canonical": None, "family": "budget",
        "reason": "total cost <= budget; one formula (`plan_cost`), hard",
    },
    "B3": {
        "status": "active", "canonical": None, "family": "transit",
        "reason": "every consecutive gap fits the matrix minutes; a missing "
                  "cell is infeasible, never 0/haversine; hard",
    },
    # Mirrors: aggregates over the rules above, never new constraints.
    "TCS": {
        "status": "active", "canonical": None, "family": "mirror",
        "reason": "time mirror over VROH/B3/ETB + no-overlap + inside "
                  "[start, deadline]; aggregate, adds no own rule",
    },
    "HCS": {
        "status": "active", "canonical": None, "family": "mirror",
        "reason": "fail-closed hard mirror (incl. must_visit/avoid); the "
                  "hard-vs-hard conflict guard stays untouched",
    },
    # Sequence / quota groups.
    "A1": {
        "status": "active", "canonical": None, "family": "meal-slot",
        "reason": "at most one restaurant per meal slot; the canonical "
                  "slot-count rule",
    },
    "CAFE_CAP": {
        "status": "active", "canonical": None, "family": "daily-count",
        "reason": "canonical cafe quota (1/day, 2 across dayparts with a "
                  "cafe need, never 3)",
    },
    "CATEGORY_CAP": {
        "status": "active", "canonical": None, "family": "daily-count",
        "reason": "canonical non-food cap (one per category per day); meals "
                  "are exempt (A1/CAFE_CAP)",
    },
    "NO_CONSECUTIVE": {
        "status": "active", "canonical": None, "family": "adjacency",
        "reason": "canonical adjacency rule: no two back-to-back POIs of the "
                  "same category; the shared scan every duplicate reads",
    },
    "NO_ADJACENT_FOOD": {
        "status": "deprecated", "canonical": "NO_CONSECUTIVE",
        "family": "adjacency",
        "reason": "strict subset of NO_CONSECUTIVE (both read `poi_category`); "
                  "kept as a named reporting view computed by the same scan "
                  "with only='restaurant'",
    },
    "REST_FOLLOWS_LUNCH": {
        "status": "active", "canonical": None, "family": "rest",
        "reason": "canonical siesta rule: start at lunch end, length by pace; "
                  "one definition (`rest_rule_violation`) for gate+validator",
    },
    # Soft layer (soft_rules.py); statuses live here so there is ONE registry.
    "F1": {
        "status": "active", "canonical": None, "family": "variety",
        "reason": ">=1 food AND >=1 sightseeing per day; SOFT (reported, "
                  "never fail-closes)",
    },
    "A2": {
        "status": "active", "canonical": None, "family": "meal-spacing",
        "reason": "canonical meal spacing: restaurants <2.5h apart (START to "
                  "START); soft pair penalty + optimizer objective",
    },
    "B1": {
        "status": "deprecated", "canonical": "NO_CONSECUTIVE",
        "family": "adjacency",
        "reason": "soft mirror of hard NO_CONSECUTIVE; survives only as the "
                  "optimizer edge weight, not as a second adjacency rule",
    },
    "B2": {
        "status": "deprecated", "canonical": ("CATEGORY_CAP", "CAFE_CAP"),
        "family": "daily-count",
        "reason": "day-level counting is owned by CATEGORY_CAP (cap 1) and "
                  "CAFE_CAP (cap 2); B2 survives as a report-only penalty for "
                  "the uncapped types (bar/spa/...)",
    },
    "E2": {
        "status": "active", "canonical": None, "family": "time-fit",
        "reason": "bar/nightlife before 17:00; unique (VROH only sees POI "
                  "hours), soft rank penalty",
    },
}

ACTIVE_RULES = tuple(name for name, meta in RULE_FREEZE.items()
                     if meta["status"] == "active")
DEPRECATED_RULES = tuple(name for name, meta in RULE_FREEZE.items()
                         if meta["status"] == "deprecated")


def rule_status(name: str) -> str:
    """`RULE_FREEZE` lookup: "active" / "deprecated" (KeyError if unknown)."""
    return RULE_FREEZE[name]["status"]


def is_deprecated(name: str) -> bool:
    return rule_status(name) == "deprecated"


def freeze_report() -> dict:
    """Registry as a report: {"active", "deprecated", "families", "rules"}."""
    families: dict[str, list[str]] = {}
    for name, meta in RULE_FREEZE.items():
        families.setdefault(meta["family"], []).append(name)
    return {"active": list(ACTIVE_RULES),
            "deprecated": list(DEPRECATED_RULES),
            "families": families,
            "rules": {name: dict(meta) for name, meta in RULE_FREEZE.items()}}


def freeze_drift(itinerary: dict, trip: dict, pois: dict,
                 matrix: dict) -> list[str]:
    """Deprecated rules that failed while their canonical owner passed.

    Must always be empty (a deprecated rule is computed FROM its canonical
    implementation). Exposed as an audit hook for tests/review instead of
    being enforced inside the request path.
    """
    results = {name: fn(itinerary, trip, pois, matrix) for name, fn in CHECKS}
    drift = []
    for name in DEPRECATED_RULES:
        if name not in results or results[name]["passed"]:
            continue
        owners = RULE_FREEZE[name]["canonical"] or ()
        owners = (owners,) if isinstance(owners, str) else tuple(owners)
        if any(not results.get(owner, {"passed": True})["passed"]
               for owner in owners):
            continue
        drift.append(name)
    return drift


def all_pass(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Compatibility summary over HARD checks: {"passed", "failed"}.

    Soft checks (F1) are surfaced by `validator.validate` under
    `soft_violations`, deliberately not here.
    """
    failed = [name for name, fn in HARD_CHECKS
              if not fn(itinerary, trip, pois, matrix)["passed"]]
    return {"passed": not failed, "failed": failed}


def report(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Full gate report for one itinerary (select / repair share this).

    {"passed", "failed", "soft_failed", "deprecated_failed", "score",
    "checks", "scores"}.
    `passed`/`failed` are HARD only (fail-closed); soft checks (F1) land in
    `soft_failed`. `deprecated_failed` names the HARD failures whose rule is
    marked deprecated in `RULE_FREEZE` (today only NO_ADJACENT_FOOD): they
    stay in `failed` for API/report compatibility, and are always implied by
    their canonical owner, never an extra constraint. `score` is the mean
    canonical score over ALL checks.
    """
    results = {name: fn(itinerary, trip, pois, matrix) for name, fn in CHECKS}
    failed = [name for name, res in results.items()
              if not res["passed"] and name not in SOFT_CHECKS]
    soft_failed = [name for name, res in results.items()
                   if not res["passed"] and name in SOFT_CHECKS]
    deprecated_failed = [name for name in failed if is_deprecated(name)]
    return {
        "passed": not failed,
        "failed": failed,
        "soft_failed": soft_failed,
        "deprecated_failed": deprecated_failed,
        "score": round(sum(res["score"] for res in results.values())
                       / len(results), 4),
        "checks": {name: res["passed"] for name, res in results.items()},
        "scores": {name: res["score"] for name, res in results.items()},
    }
