"""Canonical gate registry (T011 + T061f), shared by validator + evaluator.

ONE registry for the gate checks (fixes X8 "2 bộ cổng"): gate.py owns the
formulas, `BE/eval/metrics.py` imports `CHECKS` and reads their `score`.
Every check returns the canonical shape ``{"passed": bool, "score": float}``
with a finite score in [0, 1]:
- FAR: no activity on unknown/unverified POI (FR-013); score = verified
  ratio.
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
  B1 edge penalty). score = compliant transition ratio.
- NO_ADJACENT_FOOD: no two back-to-back `restaurant` POIs, ANY cuisine
  (BBQ->vegan included). NO_CONSECUTIVE stays for the other repeats.
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
- HCS: hard mirror — the concrete gates (incl. A1, CAFE_CAP, CATEGORY_CAP,
  NO_CONSECUTIVE, NO_ADJACENT_FOOD, REST_FOLLOWS_LUNCH) pass AND must_visit
  present AND avoid absent. Soft checks (F1) are NOT mirrored.

Inputs are the shared plain dicts (itinerary/trip/pois/matrix) used by the
validator (T049) and the tier-1 evaluator.
"""

from __future__ import annotations

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
    is_restaurant,
    is_sightseeing,
    lunch_activity,
    meal_slot,
    meal_window_present,
    poi_category,
    rest_span,
)
from BE.common import deadline, in_range, plan_cost, to_min

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


def check_far(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """Pass iff every activity uses a verified POI (non-empty plan)."""
    acts = itinerary.get("activities", [])
    if not acts:
        return _result(False, 0.0)
    bad = sum(1 for a in acts
              if a.get("poi_id") not in pois
              or not (pois.get(a["poi_id"]) or {}).get("verified"))
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
    cost = plan_cost(itinerary, pois)
    return _result(cost <= int(trip.get("budget", 0)))


def check_etb(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """`return_time` is a hard within-day deadline; min(end_time, return_time)."""
    acts = itinerary.get("activities", [])
    if not acts or not (trip.get("end_time") or trip.get("return_time")):
        return _result(True)
    last_end = max(to_min(a["end"]) for a in acts)
    return _result(last_end <= deadline(trip))


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


def check_no_consecutive(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    """HARD: no two back-to-back POIs of the same category (no exemptions).

    The categories come from `poi_category` (snapshot `cat`, legacy `type`),
    so a missing category is ignored rather than treated as "same". score =
    compliant transition ratio.
    """
    acts = _ordered(itinerary)
    if len(acts) < 2:
        return _result(True, 1.0)
    bad = 0
    for x, y in zip(acts, acts[1:]):
        left = poi_category(pois.get(x.get("poi_id")) or {})
        right = poi_category(pois.get(y.get("poi_id")) or {})
        if left and left == right:
            bad += 1
    return _result(bad == 0, 1.0 - bad / (len(acts) - 1))


def check_no_adjacent_food(itinerary: dict, trip: dict, pois: dict,
                           matrix: dict) -> dict:
    """HARD: no two back-to-back restaurants, whatever the cuisine.

    BBQ -> vegan is just as broken as two seafood places. This is the
    food-specific rule; NO_CONSECUTIVE stays for every other repeat
    (cafe->cafe, market->market, beach->beach). A missing category is
    ignored, never treated as a restaurant. score = compliant edge ratio.
    """
    acts = _ordered(itinerary)
    if len(acts) < 2:
        return _result(True, 1.0)
    bad = sum(
        1 for x, y in zip(acts, acts[1:])
        if is_restaurant(pois.get(x.get("poi_id")))
        and is_restaurant(pois.get(y.get("poi_id")))
    )
    return _result(bad == 0, 1.0 - bad / (len(acts) - 1))


def check_rest_follows_lunch(itinerary: dict, trip: dict, pois: dict,
                             matrix: dict) -> dict:
    """HARD: the siesta exists and starts at the lunch restaurant's end.

    Rest is not an activity: it is inferred from the lunch activity, exactly
    like the report/optimizer do. A plan passes iff
    - a restaurant starts inside 11:00-13:00 (the lunch),
    - no other activity overlaps [lunch_end, lunch_end + rest_minutes), and
    - the window length matches the pace (shrunk only for a late lunch,
      floor REST_MIN_FLOOR).
    A plan without an onboarding profile is legacy and has no lunch/rest
    need, so it passes vacuously (the gate never invents constraints).
    score = compliant activity ratio.
    """
    profile = trip.get("profile") or {}
    if not profile:
        return _result(True, 1.0)
    if not meal_window_present(trip, "lunch"):
        # CONDITIONAL meals: a morning half-day (or a day that cannot hold
        # the 11:30-13:30 lunch window) has no lunch, so there is no siesta
        # to follow. The gate mirrors the planner's rule instead of forcing
        # a meal the trip cannot hold.
        return _result(True, 1.0)
    acts = _ordered(itinerary)
    lunch = lunch_activity(acts, pois)
    if lunch is None:
        return _result(False, 0.0)
    span = rest_span(acts, pois, profile, deadline(trip))
    if span is None:  # defensive: lunch_activity already proved a lunch
        return _result(False, 0.0)
    declared = effective_rest(span, itinerary.get("rest"))
    lo, hi = declared["start"], declared["end"]
    # Gate-level structural checks: start at/after lunch end but no more than
    # REST_START_TOLERANCE late, and exactly the pace length (shrunk allowed
    # for a late lunch by rest_span itself).
    late = lo - span["lunch_end"]
    structural = (0 <= late <= REST_START_TOLERANCE
                  and declared["minutes"] == span["minutes"])
    others = [a for a in acts if a is not lunch]
    bad = sum(1 for a in others
              if to_min(a["start"]) < hi and to_min(a["end"]) > lo)
    if not structural:
        return _result(False, 0.0)
    return _result(bad == 0, 1.0 - bad / len(others) if others else 1.0)


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
               for check in (check_far, check_vroh, check_b3,
                             check_bcs, check_etb, check_a1,
                             check_cafe_cap, check_category_cap,
                             check_no_consecutive,
                             check_no_adjacent_food, check_rest_follows_lunch)):
        return _result(False)
    ids = [a.get("poi_id") for a in itinerary.get("activities", [])]
    if any(m in ids for m in trip.get("avoid", [])):
        return _result(False)
    must = trip.get("must_visit", [])
    if must and not all(m in ids for m in must):
        return _result(False)
    return _result(True)


CHECKS = (("FAR", check_far), ("VROH", check_vroh),
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

    {"passed", "failed", "soft_failed", "score", "checks", "scores"}.
    `passed`/`failed` are HARD only (fail-closed); soft checks (F1) land in
    `soft_failed`. `score` is the mean canonical score over ALL checks.
    """
    results = {name: fn(itinerary, trip, pois, matrix) for name, fn in CHECKS}
    failed = [name for name, res in results.items()
              if not res["passed"] and name not in SOFT_CHECKS]
    soft_failed = [name for name, res in results.items()
                   if not res["passed"] and name in SOFT_CHECKS]
    return {
        "passed": not failed,
        "failed": failed,
        "soft_failed": soft_failed,
        "score": round(sum(res["score"] for res in results.values())
                       / len(results), 4),
        "checks": {name: res["passed"] for name, res in results.items()},
        "scores": {name: res["score"] for name, res in results.items()},
    }
