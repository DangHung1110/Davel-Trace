"""Multi-profile optimizer runs + solution pool (T032, lane B; US4).

Three profiles are STRUCTURALLY DIFFERENT objectives over the same candidate
pool and the same hard gates (habitability: lunch/rest/caps/adjacency apply to
every option, so every profile stays a plan a human can actually do):

- savings  -> COST-FIRST: minimise fee + travel (avg matrix leg), reward
              free/nature/market stops, respect a tight budget harder.
- balanced -> RATING-FIRST: maximise the sum of trusted ratings (raw rating
              shrunk by its review count, BE.common.trusted_rating) plus a
              fame term, so the day is made of places people actually know.
- experience -> NOVELTY-FIRST: Vargas-style novelty (low popularity, rare
              category/tag, high fit) + a dominant category-spread term, so
              the day is composed of POIs the rating-first plan skips.

`/v1/itinerary` now returns all three by default; the router additionally
enforces a pairwise POI-set Jaccard ceiling (see `pool.enforce_pairwise`) so
the three options are genuinely different days, not three reorderings.

Each run -> validate (T018) -> score (total cost, travel time,
preference = mean rating) + profile reason + T032s `scores`
(profit/utility/gate/excluded) + a `diversity` report.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import replace

from BE.app.services import (
    matrix as matrix_svc,
    pool as pool_svc,
    profile_filter,
    response,
    retrieval,
    route_order,
    scorer,
    soft_rules,
    templates,
    trip_ctx,
)
from BE.app.services.optimizer import (
    STOP_OVERHEAD_MIN, StubTrip, optimize, poi_visit_min, poi_visit_short, poi_windows,
    stubs_from_pois)
from BE.app.services.validator import validate
from BE.common import (
    clamp01, closed_weekdays, deadline, effective_fee, hhmm, party_size, poi_on_date,
    price_level_of, to_float, to_int, to_min, trusted_rating, weekday_of)

PROFILE_REASONS = {
    "savings": "tiết kiệm: chi phí + di chuyển thấp nhất, ưu tiên điểm "
               "miễn phí/thiên nhiên/chợ",
    "balanced": "cân bằng: ưu tiên điểm được đánh giá cao và nhiều người biết, "
                "trong ràng buộc",
    "experience": "trải nghiệm: ưu tiên điểm độc đáo + trải đều loại hình "
                  "(chịu chi trong ngân sách)",
}

# Machine-readable objective per profile (also reported on every plan so a
# client can explain WHY two options differ, not just re-order).
PROFILE_OBJECTIVES = {
    "savings": "cost_first",
    "balanced": "rating_first",
    "experience": "novelty_first",
}

# --- savings: cost-first ---------------------------------------------------
# Base keeps every node score positive (the optimizer's diversity term is
# scaled by the top score, so a negative scale would invert it).
SAVINGS_BASE = 1.0
SAVINGS_FEE_UNIT = 100_000        # VND; one fee unit == one score point
SAVINGS_RATING_WEIGHT = 0.05      # rating is a weak tie-break, not the goal
SAVINGS_TRAVEL_WEIGHT = 1.0 / 60  # per minute of the average matrix leg
# The optimizer adds q_ij * 100 to an objective whose node scores are *1000,
# so this is subtracted per transition minute: a 30-minute leg costs ~1.5
# node-score points (roughly 150k VND of fee, so fee stays the primary cost
# term while travel is no longer a tie-break). The avg-leg node term alone is
# too weak when every POI is free, as in the Danang snapshot.
SAVINGS_EDGE_TRAVEL_WEIGHT = 0.5
SAVINGS_PRICE_LEVEL_PENALTY = 0.15  # per level above the cheapest band
SAVINGS_FREE_BONUS = 0.15         # a free stop is always preferred
SAVINGS_CHEAP_CATEGORY_BONUS = 0.10  # nature/market/park/beach when free
SAVINGS_CATEGORIES = frozenset({"nature", "market", "park", "beach"})
SAVINGS_FAME_WEIGHT = 0.05        # among the cheap, the place people know
TIGHT_BUDGET_VND = 1_000_000      # under this, every fee VND counts double
SAVINGS_TIGHT_FEE_MULTIPLIER = 2.0

# --- balanced: rating-first ------------------------------------------------
# Ten times the Google reviews are worth this many rating points. Trusted rating
# alone still prefers a 4.8 with 24 reviews to a 4.2 with 8,287 (Bảo tàng Chăm) and
# a 4.8 with 1,466 to a 4.5 with 16,325 (Chùa Linh Ứng). On 4 sample days of
# danang-v1, 0.4 brought those in while a 3.5 star place with 5,000 reviews
# still loses to a 4.9 with 200 (0.2 kept the lesser-known picks).
BALANCED_FAME_WEIGHT = 0.4

# --- experience: novelty-first --------------------------------------------
# Vargas-style novelty: fit * (low popularity + rare category + rare tags).
# The rating weight is deliberately small; novelty + category spread decide
# the composition. 0.10 * 4.9 = 0.49 while one novelty point is worth 10, so
# a 4.2 rare place beats a 4.9 mainstream one by a wide margin (pinned in
# test_profile_objectives). Tuned upward from 0.25/5.0 because the Danang
# verified pool is restaurant-heavy: at 0.25/5.0 the rating term still pulled
# experience back towards the rating-first composition.
EXPERIENCE_RATING_WEIGHT = 0.10
EXPERIENCE_NOVELTY_WEIGHT = 10.0
EXPERIENCE_FIT_FLOOR = 3.0        # below this a POI is not "high-fit"
EXPERIENCE_FIT_SPAN = 1.9         # 3.0 -> 0.0, 4.9 -> 1.0
EXPERIENCE_FAME_WEIGHT = 0.3      # novelty leads, but among known places

# Minutes of driving as an objective cost, per profile (`_profile_edges`). The
# optimizer adds q_ij * 100 to node scores * 1000, so at 0.3 a 30-minute leg costs
# 0.9 of a node score: against the 4.5-6.5 of a balanced stop, enough to stop a day
# crossing town twice without ruling out the one place worth the ride. It was 0 for
# these two profiles, which drove 84 minutes a day against 16 for savings.
EDGE_TRAVEL_WEIGHT = {"savings": SAVINGS_EDGE_TRAVEL_WEIGHT, "balanced": 0.3, "experience": 0.3}

# Category-spread strength per profile (optimizer TASK-1 term). Experience
# makes it dominant: a new category is worth more than another restaurant.
DIVERSITY_WEIGHT_BY_PROFILE = {
    "savings": 1.0,
    "balanced": 1.0,
    "experience": 2.5,
}

# Solver candidate cap (Phase 2). CP-SAT finds no first solution inside the
# 5 s budget at ~190 nodes (4 workers, parallel profiles), so every ladder
# rung times out and a request takes ~50 s. Measured on 193 verified POIs,
# 7 scenarios: uncapped max 51.5 s, 1 failed plan, utility 0.905; K=60/80/
# 100/120 all 0 failed, 18/18 wishes met, utility 0.953-0.963, max 5.4-6.4 s.
# 80 leaves room for score-driven picks once the category floor fills up.
# Each profile keeps its OWN best candidates (savings keeps the cheap ones),
# with a per-category floor so a wished/required category never disappears.
MAX_SOLVER_CANDIDATES = 80
CANDIDATE_FLOOR_PER_CATEGORY = 3
# What a narrow wish ("hải sản") can pick from always survives the cap.
CANDIDATE_FLOOR_PER_WISH = 6
CANDIDATE_CHEAP_MEALS = 4         # a tight budget may afford no other lunch or dinner

# Additive taste bonus for onboarding food prefs, as a fraction of the TOP POI
# score in the candidate pool (so savings ~0.5 and balanced ~5 keep the same
# meaning; one knob stays one knob). Applied to the optimizer node score, not
# only to rank, so a taste hit can win a slot against a slightly higher rating.
#
# TUNING (TASK-2, "teeth"): the unit is SIGNED (-1 exclusive cuisine clash ..
# +1 every pref matched) and 0 for non-food POIs. A 0.4 rating gap costs
# 0.4 rating points (balanced) / 0.04 (savings, rating*0.1); a full hit at
# 0.20 * unit = 0.98 / 0.098 wins both, so a 4.5 seafood place outranks a 4.9
# BBQ joint for a seafood profile (pinned in test_taste_scoring.py). A clash
# costs the same, so a 4.9 vegan-only kitchen loses to a 4.2 seafood place.
TASTE_WEIGHT = 0.20

# The onboarding's other SOFT answers ("SOFT — trọng số điểm" on the page):
# spending_level, outdoor_bias and the liked activities. They reached only the rank
# list, which orders candidates and explains them, so the day came out the same
# whatever was answered: on 12 real days the restaurants had the same price level
# at spending 1, 2 and 3 in 10. Each is now a signed lean on the node score, in
# units of the top POI score like TASTE_WEIGHT, and zero for the neutral answer
# (level 2, bias 0, nothing ticked), so a profile that says nothing plans as before.
# - spending: +/- for a priced place (restaurant, cafe, bar, spa) dearer or cheaper
#   than such places usually are in the pool, towards what the level asks for.
# - outdoor: bias (-1..1) on what `soft_rules.is_outdoor` calls outdoor.
# - liked: a POI that answers a liked activity (`retrieval.poi_is_liked`), worth
#   what a full taste hit is.
# A lean chooses between places; it never adds a stop the rules do not ask for.
# Measured on danang-v1 (4 parties x 3 plans, then the page's 3 cards x 3 plans):
#   spending 1 against 3: the day's priced stops cost more at 3 in 12 of 12 plans
#     (mean price level 1.02 against 1.82); they cost the same in 11 of 12 before.
#   outdoor -1 / 0 / +1: 2.7 / 3.3 / 6.3 stops out of doors a day, never fewer for
#     a higher bias in any of the 12; before 3.0 / 3.3 / 3.1, in no order.
#   liked: 25 stops in a liked category on the 9 card plans against 16 with the
#     likes blanked, none of the 9 with fewer (19 against 18 before; at 0.15 one
#     plan had fewer, 0.25 gave 27).
SPENDING_WEIGHT = 0.15
OUTDOOR_WEIGHT = 0.15
LIKED_WEIGHT = 0.20

# A rung that ran out of search budget with no solution (`status: unknown`) says
# nothing about its rules. Two in a row say the pool is too hard for the budget:
# the ladder stops there instead of paying the full budget on every rung left
# (20 rungs x 6 s was a minute of nothing), and the plan says so. While the rungs
# still carry the traveller's wishes, it is the wishes the budget cannot seat (a
# seven-hour park next to a lunch and a dinner): those rungs are skipped and the day
# is planned without them, reported unmet, instead of no plan at all.
MAX_UNKNOWN_RUNGS = 2
# A diagnosis only names the rule that killed a plan: small budgets each.
DIAGNOSE_TIMEOUT_S = 2.0
DIAGNOSE_WALL_GUARD_S = 30.0      # by work the wall clock must not decide the answer
DIAGNOSE_DETERMINISTIC_TIME = 2.0
WEEKDAY_LABELS = ("thu 2", "thu 3", "thu 4", "thu 5", "thu 6", "thu 7", "chu nhat")
# What the ranker says AGAINST a stop at some hour (rank.py, trip_ctx). Not evidence.
AGAINST_REASONS = frozenset({
    "nong, tranh ngoai troi", "nang gat buoi trua", "mua, han che ngoai troi",
    "dip chieu, chi di nhe", "vua an, chi hop do nhe", "no, vua an xong",
    "bar/ nightlife truoc 17h", "han che ngoai troi",
})


def novelty_scores(pois: list[dict]) -> dict[str, float]:
    """Vargas-style novelty in [0, 1] for every POI in a candidate pool.

    novelty = fit * (0.55 * (1 - popularity) + 0.30 * category-rarity
                     + 0.15 * tag-rarity)

    - fit: rating above EXPERIENCE_FIT_FLOOR, normalised (3.0 -> 0, 4.9 -> 1).
      A poorly-rated POI is not "novel", it is just bad; the fit factor keeps
      the novelty term from rewarding junk.
    - popularity: where the POI's rating sits in the pool (a 4.9 place is
      mainstream) plus a must_go bump. Inverse = novelty.
    - category-rarity: 1 - sqrt(share of the category in the pool), so a
      beach/attraction beats a restaurant in a restaurant-heavy pool.
    - tag-rarity: mean inverse document frequency of the POI's tags, which
      separates a one-off seafood shack from a generic "Nhà hàng" listing.
    """
    pool = list(pois)
    if not pool:
        return {}
    n = len(pool)
    cats = Counter(soft_rules.poi_category(p) for p in pool)
    tag_freq: Counter[str] = Counter()
    for p in pool:
        for tag in {str(t).strip().lower() for t in (p.get("tags") or [])
                    if str(t).strip()}:
            tag_freq[tag] += 1
    ratings = [trusted_rating(p) for p in pool]
    lo, hi = min(ratings), max(ratings)

    def _tag_rarity(p: dict) -> float:
        tags = [str(t).strip().lower() for t in (p.get("tags") or [])
                if str(t).strip()]
        if not tags:
            return 0.0
        # Smoothed IDF, normalised into [0, 1] by log(n + 1).
        return sum(math.log((1.0 + n) / (1.0 + tag_freq[t])) / math.log(1.0 + n)
                   for t in set(tags)) / len(set(tags))

    out: dict[str, float] = {}
    for p in pool:
        cat = soft_rules.poi_category(p)
        rating = trusted_rating(p)
        fit = clamp01((rating - EXPERIENCE_FIT_FLOOR) / EXPERIENCE_FIT_SPAN)
        popularity = ((rating - lo) / (hi - lo)) if hi > lo else 0.5
        if p.get("must_go"):
            popularity = min(1.0, popularity + 0.25)
        cat_rarity = (1.0 - math.sqrt(cats[cat] / n)) if cat else 0.0
        novelty = fit * (0.55 * (1.0 - popularity)
                         + 0.30 * cat_rarity
                         + 0.15 * _tag_rarity(p))
        out[p["poi_id"]] = round(clamp01(novelty), 4)
    return out


def _avg_leg(travel: dict[tuple[str, str], int], pid: str,
             ids: list[str]) -> float:
    """Mean matrix minutes from `pid` to every other candidate (bidirectional).

    A cheap proxy for "how much driving this stop costs" that the NODE score
    can see. The real route is still chosen (and validated) by the solver;
    this only makes savings prefer a compact cluster.
    """
    legs = []
    for other in ids:
        if other == pid:
            continue
        leg = travel.get((pid, other))
        if leg is None:
            leg = travel.get((other, pid))
        if leg is not None:
            legs.append(float(leg))
    return sum(legs) / len(legs) if legs else 0.0


def _profile_edges(profile: str, q: dict[tuple[str, str], float],
                   travel: dict[tuple[str, str], int]
                   ) -> dict[tuple[str, str], float]:
    """Profile-specific transition scores.

    Every profile subtracts the matrix leg time from q_ij, so the solver weighs
    the real tour against what a stop is worth (`EDGE_TRAVEL_WEIGHT`).
    """
    weight = EDGE_TRAVEL_WEIGHT.get(profile, 0.0)
    if not weight:
        return q
    return {(a, b): round(value - travel.get((a, b), 0) * weight, 4)
            for (a, b), value in q.items()}


def _score(profile: str, p: dict, novelty: dict[str, float] | None = None,
           avg_leg: float = 0.0, budget: float | None = None) -> float:
    """Node score for one profile (see module docstring).

    savings: absolute cost minimisation (fee + travel), not a tie-break.
    balanced: trusted rating + fame, constraints respected.
    experience: novelty-first with a dominant category-spread term in the
    optimizer (`DIVERSITY_WEIGHT_BY_PROFILE`); the node score itself is
    novelty + a small rating/fit term.
    """
    rating, known_fee = trusted_rating(p), effective_fee(p)
    fee = known_fee or 0
    if profile == "savings":
        cat = soft_rules.poi_category(p)
        price_level = price_level_of(p)  # null = unknown -> middle band
        fee_weight = SAVINGS_FEE_UNIT
        if budget is not None and 0 < float(budget) < TIGHT_BUDGET_VND:
            fee_weight = fee_weight / SAVINGS_TIGHT_FEE_MULTIPLIER
        score = SAVINGS_BASE - (fee / fee_weight)
        score -= avg_leg * SAVINGS_TRAVEL_WEIGHT
        score -= max(0, price_level - 1) * SAVINGS_PRICE_LEVEL_PENALTY
        score += rating * SAVINGS_RATING_WEIGHT
        score += SAVINGS_FAME_WEIGHT * math.log10(1 + int(p.get("review_count") or 0))
        if known_fee == 0:
            score += SAVINGS_FREE_BONUS
            if cat in SAVINGS_CATEGORIES:
                score += SAVINGS_CHEAP_CATEGORY_BONUS
        return round(score, 4)
    if profile == "experience":
        nov = float((novelty or {}).get(p.get("poi_id"), 0.0))
        return round(rating * EXPERIENCE_RATING_WEIGHT
                     + EXPERIENCE_FAME_WEIGHT * math.log10(1 + int(p.get("review_count") or 0))
                     + nov * EXPERIENCE_NOVELTY_WEIGHT, 4)
    # balanced: rating-first
    fame = math.log10(1 + int(p.get("review_count") or 0))
    return round(rating + BALANCED_FAME_WEIGHT * fame, 4)


def price_reference(pois: list[dict]) -> dict[str, int]:
    """What a priced place usually costs in this pool: the median price level of
    each priced category (restaurants 2, cafes 1 on danang-v1). `soft_lean` reads a
    place against it, so "cheap" means cheap for a restaurant, not cheaper than a park."""
    levels: dict[str, list[int]] = {}
    for poi in pois:
        cat = soft_rules.poi_category(poi)
        if cat in retrieval.PAID_CATS:
            levels.setdefault(cat, []).append(price_level_of(poi))
    return {cat: sorted(values)[len(values) // 2] for cat, values in levels.items()}


def soft_lean(poi: dict, profile: dict | None, liked: list[str] | None = None,
              price_ref: dict[str, int] | None = None) -> tuple[float, list[str]]:
    """(lean, reasons) of the onboarding's soft answers for one POI.

    `lean` is signed, in units of the top POI score (see SPENDING_WEIGHT); the
    reasons are those that speak FOR the stop, for its explanation. A neutral
    profile (spending 2, bias 0, no liked activity) gives (0.0, []) for every POI.
    `liked`: `retrieval.liked_wishes(profile["activities"])`; `price_ref`:
    `price_reference(pool)`.
    """
    profile = profile or {}
    lean, reasons = 0.0, []
    cat = soft_rules.poi_category(poi)
    wants = to_int(profile.get("spending_level"), 2) - 2          # -1 thrifty .. +1 premium
    if wants and cat in retrieval.PAID_CATS:
        dearer = max(-1, min(1, price_level_of(poi) - (price_ref or {}).get(cat, 2)))
        lean += SPENDING_WEIGHT * wants * dearer
        if wants * dearer > 0:
            reasons.append("hop muc chi tieu")
    bias = max(-1.0, min(1.0, to_float(profile.get("outdoor_bias"))))
    if bias and soft_rules.is_outdoor(poi):
        lean += OUTDOOR_WEIGHT * bias
        if bias > 0:
            reasons.append("hop gu ngoai troi")
    if liked and retrieval.poi_is_liked(poi, liked):
        lean += LIKED_WEIGHT
        reasons.append("hop hoat dong ban thich")
    return round(lean, 4), reasons


def plan_diversity(activities: list[dict], pois: list[dict],
                   profile: str) -> dict:
    """Composition evidence: distinct categories + mean novelty of the stops.

    `novelty` is the mean of `novelty_scores` over the STOPPED POIs (meals
    included, because a novel meal is still a novel experience), and
    `distinct_categories` is the count of different canonical categories.
    """
    by_id = {p["poi_id"]: p for p in pois}
    nov = novelty_scores(pois)
    cats = [soft_rules.poi_category(by_id.get(a.get("poi_id")))
            for a in activities]
    cats = [c for c in cats if c]
    values = [nov.get(a.get("poi_id"), 0.0) for a in activities]
    return {
        "objective": PROFILE_OBJECTIVES.get(profile, "rating_first"),
        "distinct_categories": len(set(cats)),
        "categories": sorted(set(cats)),
        "novelty": round(sum(values) / len(values), 4) if values else 0.0,
        "novel_stops": sum(1 for value in values if value >= 0.30),
    }


def score_plan(plan: dict) -> dict:
    """Profit/Utility + gate (T032s, lane B; TravelEval-style).

    profit = preference per million VND (value-for-money; savings wins
    tight budgets). utility = 0.7 preference/5 + 0.3 route efficiency
    (1 - travel_min/600; experience wins preference-heavy asks).
    Gate fail (any constraint_status != 1) -> excluded, scores zeroed.
    """
    gate = bool(plan.get("constraint_status")) and all(
        v == 1 for v in plan["constraint_status"].values())
    if not gate:
        return {"profit": 0.0, "utility": 0.0, "gate": False, "excluded": True}
    pref = float(plan.get("preference", 0.0))
    profit = pref / (1.0 + float(plan.get("total_cost", 0)) / 1000000.0)
    route_eff = max(0.0, 1.0 - float(plan.get("travel_min", 0)) / 600.0)
    utility = 0.7 * (pref / 5.0) + 0.3 * route_eff
    return {"profit": round(profit, 4), "utility": round(utility, 4),
            "gate": True, "excluded": False}


def _to_trip(trip: dict) -> StubTrip:
    """Open tour: the seed matrix has no depot cell (optimizer T061a)."""
    return StubTrip(to_min(trip.get("start_time", "07:00")), deadline(trip), None)


def _max_fee(trip: dict) -> int | None:
    """Gate BCS as a per-person fee ceiling for the solver (no budget -> none)."""
    budget = trip.get("budget")
    return None if budget is None else int(budget) // party_size(trip)


def _within_budget(out: dict, stubs: list, trip: dict) -> bool:
    """Does this optimizer result respect the trip's fee ceiling?"""
    fees = {stub.poi_id: stub.fee for stub in stubs}
    ceiling = _max_fee(trip)
    return ceiling is None or sum(fees.get(a["poi_id"], 0)
                                  for a in out["itinerary"]["activities"]) <= ceiling


def _all_day_minutes(ids, pois_by_id: dict) -> int:
    """Minutes an all-day place takes out of the day when the traveller named one:
    the longest all-day stay among `ids` (0 = none of them is an all-day place)."""
    stays = [poi_visit_min(pois_by_id[pid]) for pid in ids or [] if pid in pois_by_id]
    return max((stay for stay in stays if stay >= soft_rules.ALL_DAY_MIN), default=0)


def _limits(tpl_name: str | None, trip: dict, busy_min: int = 0) -> dict:
    """The day's limits: its archetype's, else the universal human needs."""
    return (templates.template_constraints(tpl_name, trip, busy_min) if tpl_name
            else templates.universal_constraints(trip, busy_min))


def _ladder(limits: dict, act_groups: list[dict], must: list[str] | None = None,
            wished_limits: dict | None = None) -> list[tuple[int, dict, str, bool]]:
    """Template ladder with the trip's activity groups riding along.

    The user's own wishes outrank the template's inferred counts: every
    template rung is tried WITH the activity groups first. Then the same rungs
    with the wished POIs freed from their sensible hours (a beach is what was asked
    for, even at noon), and only when none fits are the wishes dropped (the plan
    then reports them as unmet). Dinner goes last, with a warning: money or hours
    may not hold a second meal, and no plan helps nobody. A place the traveller
    named that still does not fit gets its shortest usual stay, also with a warning.
    `wished_limits`: the limits of the wished rungs when a wish can only be met by an
    all-day place (its pace floor then counts the rest of the day only).
    Returns (template_step, limits, stubs, wished) so `relaxed_step` keeps its meaning,
    with stubs "plain", "any_hour" or "short" and `wished` True while the rung still
    carries the activity groups; a rung identical to an earlier one (legacy NO_LIMITS)
    is not re-solved.
    """
    plain = list(enumerate(templates.attempts(limits)))
    wished = [(step, {**rung, "required_any": list(rung["required_any"]) + act_groups})
              for step, rung in enumerate(templates.attempts(wished_limits or limits))
              ] if act_groups else []
    no_dinner = (lambda rows: [(step, {**rung, "dinner_required": False}, "plain") for step, rung in rows]) \
        if limits.get("dinner_required") else (lambda rows: [])
    rungs = [(step, rung, "plain", True) for step, rung in wished]
    rungs += [(step, rung, "any_hour", True) for step, rung in wished]
    rungs += [(*row, True) for row in no_dinner(wished)]
    rungs += [(step, rung, "plain", False) for step, rung in plain]
    rungs += [(*row, False) for row in no_dinner(plain)]
    if must:
        step, last = plain[-1]
        rungs.append((step, {**last, "dinner_required": False}, "short", False))
    out: list[tuple[int, dict, str, bool]] = []
    for step, rung, kind, with_wishes in rungs:
        if all(rung != seen or kind != used for _, seen, used, _w in out):
            out.append((step, rung, kind, with_wishes))
    return out


def _activity_match(acts: list[dict], report: list[dict],
                    pois_by_id: dict) -> list[dict]:
    """Per-activity outcome on THIS plan: "required" becomes met/unmet."""
    stops = {a.get("poi_id"): to_min(a["start"]) for a in acts}
    cats = {soft_rules.poi_category(pois_by_id.get(pid, {})) for pid in stops}
    out = []
    for entry in report:
        entry = dict(entry)
        ids = entry.pop("poi_ids", None)
        if entry["status"] == "required":
            span = entry.pop("start_between", None)
            hits = ([pid for pid in ids if pid in stops
                     and (not span or span[0] <= stops[pid] < span[1])]
                    if ids is not None else None)
            met = bool(hits) if ids is not None else bool(cats & set(entry["categories"]))
            entry["status"] = "met" if met else "unmet"
            if hits:
                entry["poi_id"] = hits[0]
        out.append(entry)
    return out


def _activity_warnings(match: list[dict]) -> list[str]:
    """Assumption-style lines for activities the plan could not honour."""
    lines = []
    for entry in match:
        cats = ", ".join(entry["categories"])
        if entry["status"] == "unmet":
            lines.append(f"khong xep duoc hoat dong '{entry['activity']}' ({cats}) "
                         "cung rang buoc cung, da bo yeu cau nay")
        elif entry["status"] == "outside_trip_hours":
            lines.append(f"'{entry['activity']}' chi co y nghia trong khung "
                         f"{hhmm(entry['start_between'][0])}-{hhmm(entry['start_between'][1])}, "
                         "ngoai khung gio cua chuyen di")
        elif entry["status"] == "over_budget":
            lines.append(f"ngan sach khong du cho hoat dong '{entry['activity']}'")
        elif entry["status"] == "no_verified_poi":
            lines.append(f"chua co diem da xac minh phu hop voi hoat dong "
                         f"'{entry['activity']}' trong khung gio nay")
        elif entry["status"] == "blocked_by_profile":
            lines.append(f"ho so nay khong xep hoat dong '{entry['activity']}' "
                         "(vuot suc hoac bi loai boi ho so)")
        elif entry["status"] == "not_understood":
            lines.append(f"chua hieu hoat dong '{entry['activity']}', bo qua")
    return lines


# What the gate registry reads off a POI: FAR/BCS/VROH, the category for
# A1/caps, and the PROFILE_SAFE haystack (tags/cuisine/ambience/smart_tags/
# intensity, the same fields profile_filter.hard_filter matched).
_GATE_EXTRA = ("tags", "cuisine", "ambience", "smart_tags", "intensity", "ticket_vnd",
               "subcat", "plan_tier", "closed_today")


def _gate_view(p: dict) -> dict:
    view = {"verified": p.get("verified", False), "fee": p.get("fee", 0),
            "opening_hours": p.get("opening_hours", []),
            "type": p.get("type", ""), "cat": p.get("cat", "")}
    view.update({k: p[k] for k in _GATE_EXTRA if k in p})
    return view


def _cap_candidates(candidates: list[dict], score, must: list[str],
                    limit: int = MAX_SOLVER_CANDIDATES,
                    floor: int = CANDIDATE_FLOOR_PER_CATEGORY,
                    wish_groups: list[dict] | None = None,
                    cheap_meals: int = 0) -> list[dict]:
    """Stratified top-K for the solver, in the incoming (rank) order.

    Kept: every must_visit, the best POIs of every wish, the `floor` best of every
    category (so the lunch restaurants survive), the `cheap_meals` cheapest restaurants,
    then the best by `score` up to `limit`. A pool at or under the limit is returned
    unchanged.
    """
    if len(candidates) <= limit:
        return candidates
    best = sorted(candidates, key=lambda p: (-score(p), p["poi_id"]))
    must_ids = set(must)
    kept = {p["poi_id"] for p in candidates if p["poi_id"] in must_ids}
    for group in wish_groups or []:
        wanted = set(group.get("poi_ids") or [])
        kept.update([p["poi_id"] for p in best if p["poi_id"] in wanted][:CANDIDATE_FLOOR_PER_WISH])
    meals = sorted((p for p in best if soft_rules.poi_category(p) == "restaurant"),
                   key=lambda p: effective_fee(p) or 0)
    kept.update(p["poi_id"] for p in meals[:cheap_meals])
    per_cat: Counter = Counter()
    for poi in best:
        cat = soft_rules.poi_category(poi)
        if per_cat[cat] < floor:
            per_cat[cat] += 1
            kept.add(poi["poi_id"])
    for poi in best:
        if len(kept) >= limit:
            break
        kept.add(poi["poi_id"])
    return [p for p in candidates if p["poi_id"] in kept]


def _travel_from_cells(cells: dict, ids: list[str]) -> dict:
    """T061a: matrix cells -> {(a,b): minutes}; a missing cell stays ABSENT (B3)."""
    return matrix_svc.travel_minutes(cells, ids)


def build_plan(profile: str, trip: dict, ranked: list[dict],
               pois_by_id: dict, cells: dict, workers: int = 0,
               template: str | None = None, ctx: dict | None = None,
               pool_size: int = 1,
               timeout_s: float | None = None,
               deterministic_time: float | None = None,
               distinct_from: list[frozenset[str]] | None = None,
               max_rung: int | None = None,
               diagnose: bool = True) -> dict:
    """One profile -> one real plan dict (POST /v1/itinerary and the eval).

    Adapts the ranked candidate POIs, runs the optimizer as an OPEN tour, validates and
    shapes the response with per-activity explanations. The endpoint owns
    `itinerary_id`/`trip_id`/`profile`; this returns the body they are attached to.

    - `template`: one of the three names, or "" for a request with no onboarding; None
      derives it from `trip["profile"]` when there is one. Its hard bans (allowed
      categories, intensity ceiling) filter the candidates BEFORE the solver, its pace
      band / required categories / late end constrain the model. A small pool relaxes
      stop and required counts (reported), never the bans.
    - `food_prefs` add a SIGNED taste bonus to each node score (`TASTE_WEIGHT`,
      `profile_filter.taste_score`): enough to beat a ~0.4 rating gap, so taste wins a
      slot instead of only re-ordering the rank list.
    - `ctx` (`trip_ctx.build`) turns on the dynamic state layer: a satiety-aware food
      penalty in the transition scores and per-band multipliers in the objective, with
      `user_state` evidence on the plan. No ctx keeps the plain planning output.
    - Universal human needs are solver constraints for EVERY profile: exactly one lunch
      restaurant in 11:00-13:00, a rest window STARTING at its END (60/45/30 min by pace,
      shrunk to fit a late lunch, floor 20), at most one dinner restaurant, the cafe
      quota, one non-food POI per category a day, no consecutive same-category stops. They
      never relax: an infeasible pool is an honest empty plan plus a warning naming the
      constraint, never a silently broken schedule.
    - `pool_size` > 1 asks for a solution pool; every member is built into a full plan
      and attached privately as `_pool_plans` (the router's diverse mode picks from it).
    - `timeout_s` / `deterministic_time` / `workers` go to CP-SAT.
    - `distinct_from` (router refill): every returned day keeps POI-set Jaccard <=
      `pool.MAX_PAIRWISE_JACCARD` to these sets, a HARD constraint. `max_rung` caps the
      ladder at the rung the replaced plan used (private `_rung`), so an alternative never
      drops a wish or a template rule the original kept. No infeasibility diagnosis runs
      in that mode, nor with `diagnose=False`, for a caller that will try again.
    """
    prof = profile if profile in PROFILE_REASONS else "balanced"
    # Everything below sees the POIs as they are on this date: that weekday's hours,
    # or closed. A must_visit closed that day leaves the plan with a warning, so the
    # rest of the day still gets planned.
    date_warnings: list[str] = []
    if weekday_of(trip.get("date")) is not None:
        pois_by_id = {pid: poi_on_date(p, trip["date"]) for pid, p in pois_by_id.items()}
        closed_must = [m for m in trip.get("must_visit") or []
                       if (pois_by_id.get(m) or {}).get("closed_today")]
        if closed_must:
            trip = {**trip, "must_visit": [m for m in trip["must_visit"] if m not in closed_must]}
            date_warnings = [f"khong dua vao lich '{pois_by_id[m].get('name')}': nghi vao "
                             f"ngay {trip['date']}" for m in closed_must]
    tpl_name = template
    if tpl_name is None:  # direct callers: derive only from an explicit profile
        tpl_name = (templates.select_template(trip["profile"])
                    if trip.get("profile") else "")
    if tpl_name not in templates.DAY_TEMPLATES:
        tpl_name = None  # "" / unknown / no profile -> legacy (no archetype)
    # A custom profile with no archetype still gets the universal lunch + rest
    # lock; a request with no profile at all stays fully legacy. A named all-day
    # place (Bà Nà) leaves only the evening for the other stops.
    limits = _limits(tpl_name, trip, _all_day_minutes(trip.get("must_visit"), pois_by_id))

    # Fail closed: the pool is exactly the ranked (verified, hard-filtered)
    # candidates. An empty pool is an honest empty plan, never "every POI"
    # (that fallback re-admitted unverified and allergy-dropped POIs).
    ranked_ids = [r.get("poi_id") for r in ranked]
    candidates = [pois_by_id[pid] for pid in ranked_ids if pid in pois_by_id
                  and not pois_by_id[pid].get("closed_today")]

    # Template hard bans: nightlife/spa for a family day, trek for a calm one. A
    # wish the traveller typed lifts the taste part of a ban (`allows_wished`).
    activities = trip.get("activities") or []
    profile_data = trip.get("profile") or {}
    banned: list[dict] = []
    if tpl_name:
        kept = []
        for poi in candidates:
            wished = any(retrieval.poi_fits_wish(poi, a) for a in activities)
            if templates.allows(poi, tpl_name) or (
                    wished and templates.allows_wished(poi, tpl_name, profile_data)):
                kept.append(poi)
            else:
                banned.append(poi)
        candidates = kept
    # What the budget can never pay for must not take a place from what it can:
    # the candidate cap keeps the best of each category, whatever they cost.
    ceiling = _max_fee(trip)
    # Retrieval has already dropped most of these: the wish report still needs them.
    unaffordable: list[dict] = []
    if ceiling is not None:
        unaffordable = [p for p in pois_by_id.values() if (effective_fee(p) or 0) > ceiling
                        and p["poi_id"] not in (trip.get("must_visit") or [])]
        out_of_reach = {p["poi_id"] for p in unaffordable}
        candidates = [p for p in candidates if p["poi_id"] not in out_of_reach]
    ids = [p["poi_id"] for p in candidates]

    # Activities -> "at least one stop of these categories" (FR-006: a
    # preference the ladder may relax with a warning, never a pool filter).
    act_groups, act_report = retrieval.activity_requirements(
        activities, candidates, banned, unaffordable,
        horizon=(to_min(trip.get("start_time", "07:00")), deadline(trip)))

    if not candidates:
        plan = _assemble([], {"itinerary": None,
                              "reason": "khong co POI da xac minh nao qua bo loc"},
                         trip, pois_by_id, cells, ranked, tpl_name, limits, 0,
                         soft_rules.cafe_cap(trip.get("profile") or {}), ctx,
                         prof, candidates, {})
        plan["infeasible_by"] = {"rule": "EMPTY_POOL",
                                 "label": "pool rong sau bo loc cung"}
        plan["activity_match"] = _activity_match([], act_report, pois_by_id)
        plan["warnings"] = (date_warnings + list(plan.get("warnings") or [])
                            + _activity_warnings(act_report))
        return plan

    travel = _travel_from_cells(cells, ids)
    nov = novelty_scores(candidates)
    budget = trip.get("budget")
    avg_legs = {pid: _avg_leg(travel, pid, ids) for pid in ids}
    base_scores = {pid: _score(prof, pois_by_id[pid], novelty=nov,
                               avg_leg=avg_legs[pid], budget=budget)
                   for pid in ids}
    unit = max((abs(v) for v in base_scores.values()), default=1.0) or 1.0
    prefs = list(profile_data.get("food_prefs") or []) or list(
        trip.get("food_prefs") or [])
    # A food wish phrased as an activity ("ăn hải sản") is a taste pref too.
    for activity in trip.get("activities") or []:
        prefs += [t for t in profile_filter.cuisine_terms(activity)
                  if t not in prefs]

    # The profile's other soft answers, once per POI of the pool (before the cap,
    # so what the traveller leans to survives it).
    liked = retrieval.liked_wishes(profile_data.get("activities"))
    price_ref = price_reference(candidates)
    leans = {p["poi_id"]: soft_lean(p, profile_data, liked, price_ref) for p in candidates}

    def _score_with_taste(poi: dict) -> float:
        unit_delta, _hits, _clashes = profile_filter.taste_score(poi, prefs)
        return (base_scores[poi["poi_id"]] + TASTE_WEIGHT * unit * unit_delta
                + unit * leans[poi["poi_id"]][0])

    capped = _cap_candidates(candidates, _score_with_taste,
                             list(trip.get("must_visit") or []), wish_groups=act_groups,
                             cheap_meals=CANDIDATE_CHEAP_MEALS if ceiling is not None else 0)
    if len(capped) < len(candidates):
        candidates = capped
        ids = [p["poi_id"] for p in candidates]
        keep = set(ids)
        travel = {pair: minutes for pair, minutes in travel.items()
                  if pair[0] in keep and pair[1] in keep}
    # A place the traveller named is held to its opening hours only; a wish may
    # also use that freedom when nothing else fits it (`_ladder`).
    must_ids = set(trip.get("must_visit") or [])
    stubs = stubs_from_pois(candidates, trip, _score_with_taste,
                            deadline=deadline(trip), any_hour_ids=must_ids)
    wish_ids = {pid for group in act_groups for pid in group.get("poi_ids") or []}
    wish_stubs = (stubs_from_pois(candidates, trip, _score_with_taste, deadline=deadline(trip),
                                  any_hour_ids=must_ids | wish_ids) if wish_ids else stubs)
    q = _profile_edges(prof, scorer.edge_scores(ids, pois_by_id, ctx=ctx),
                       travel)
    # Dynamic state: same per-band multipliers the ranker scores against,
    # but here the solver chooses the band the stop lands in. A request with no
    # profile keeps the plain planning, except in the rain: a forecast that calls
    # some hours wet moves open-air stops out of them for every traveller.
    state_bands, state_scores = ((None, None) if not (ctx or {}).get("dynamic_state")
                                 else trip_ctx.optimizer_state(ctx, candidates))
    state_costs = None
    if trip_ctx.is_wet(ctx):
        state_bands = trip_ctx.state_bands(ctx)
        state_costs = trip_ctx.rain_costs(ctx, candidates)
    must = list(trip.get("must_visit") or [])
    # HARD cafe quota mirrored into the solver (gate CAFE_CAP): the profile's
    # cafe need decides between 1 and 2 cafes; NO_CONSECUTIVE is always on.
    cafe_cap = soft_rules.cafe_cap(profile_data)
    # HARD per-category daily cap mirrored into the solver (gate CATEGORY_CAP):
    # one market/landmark/beach/attraction/... per day, universal, meals
    # exempt. Never relaxed by the ladder (attempts() does not carry it).
    category_cap = soft_rules.CATEGORY_DAILY_CAP

    # Ladder: full template -> drop pace/required counts -> drop max too.
    out: dict = {"itinerary": None, "reason": "khong co ung vien"}
    relaxed_step = 0
    rung_used = None
    solver_opts = {}
    if timeout_s is not None:
        solver_opts["timeout_s"] = float(timeout_s)
    if deterministic_time is not None:
        solver_opts["deterministic_time"] = float(deterministic_time)
    if distinct_from:
        solver_opts["distinct_from"] = list(distinct_from)
        solver_opts["distinct_ceiling"] = pool_svc.MAX_PAIRWISE_JACCARD
    # A wish only an all-day place can meet ("cáp treo"): its rungs ask the pace
    # floor of the evening that is left, the rungs without the wish of the whole day.
    wish_busy = max((min((_all_day_minutes([pid], pois_by_id) for pid in group["poi_ids"]), default=0)
                     for group in act_groups if group.get("poi_ids")), default=0)
    rungs = _ladder(limits, act_groups, must,
                    _limits(tpl_name, trip, wish_busy) if wish_busy else None)
    short_stubs = [replace(stub, visit_min=poi_visit_short(pois_by_id[stub.poi_id]))
                   if stub.poi_id in must_ids else stub for stub in stubs]
    stubs_by_kind = {"plain": stubs, "any_hour": wish_stubs, "short": short_stubs}
    if max_rung is not None:
        rungs = rungs[:max_rung + 1]
    order_prefs = [tuple(pair) for pair in trip.get("order_prefs") or [] if len(pair) == 2]
    limits_used = limits
    stubs_used = stubs
    unknown_rungs = 0
    wishes_given_up = False
    for rung, (step, limits_try, kind, with_wishes) in enumerate(rungs):
        if with_wishes and wishes_given_up:
            continue
        stubs_try = stubs_by_kind[kind]
        out = optimize(stubs_try, travel, _to_trip(trip),
                       edge_scores=q, workers=workers, must_visit=must,
                       precedence=order_prefs,
                       min_stops=limits_try["min_stops"],
                       max_stops=limits_try["max_stops"],
                       required_any=limits_try["required_any"],
                       rest_after_lunch=(limits_try.get("rest_minutes")
                                         if limits_try.get(
                                             "rest_after_lunch") else None),
                       late_end_min=limits_try["late_end_min"],
                       cafe_cap=cafe_cap, no_consecutive=True,
                       no_adjacent_food=True,
                       lunch_required=bool(limits_try.get("lunch_required")),
                       dinner_required=bool(limits_try.get("dinner_required")),
                       state_bands=state_bands,
                       state_score=state_scores,
                       state_cost=state_costs,
                       category_cap=category_cap,
                       diversity_weight=DIVERSITY_WEIGHT_BY_PROFILE.get(prof),
                       max_fee=_max_fee(trip),
                       solution_pool=pool_size,
                       **solver_opts)
        if out.get("itinerary") is not None:
            relaxed_step = step
            rung_used = rung
            limits_used = limits_try
            stubs_used = stubs_try
            break
        unknown_rungs = unknown_rungs + 1 if out.get("status") == "unknown" else 0
        if unknown_rungs >= MAX_UNKNOWN_RUNGS:
            if not with_wishes:
                break
            wishes_given_up, unknown_rungs = True, 0

    def _diagnose(base_limits: dict) -> dict | None:
        """Which single HARD rule makes this pool infeasible? (diagnostic only)

        The ladder above already relaxed the pace band / required categories
        (soft-ish template knobs). If the plan is still empty, try relaxing
        exactly ONE hard rule at a time, cheapest-first and capped first, and
        report the FIRST relaxation that yields a plan. Nothing here ever
        reaches the returned plan: it exists so the warning can say WHICH cap
        killed it instead of a vague "vo nghiem", and so nobody is tempted to
        widen the cap silently (the cap stays; the plan stays empty).
        """
        trials = (
            ("BUDGET", "ngan sach khong du cho cac diem bat buoc",
             {"max_fee": None}),
            ("CATEGORY_CAP",
             "cap HARD 1 diem/loai/ngay (market/landmark/beach/attraction/"
             "temple/museum/park/viewpoint)", {"category_cap": None}),
            ("CAFE_CAP", f"cap HARD {cafe_cap} quan cafe/ngay",
             {"cafe_cap": None}),
            ("NO_CONSECUTIVE", "khong 2 diem cung loai lien tiep",
             {"no_consecutive": False}),
            ("NO_ADJACENT_FOOD", "khong 2 nha hang lien nhau",
             {"no_adjacent_food": False}),
            ("REST_FOLLOWS_LUNCH", "khoa nghi trua ngay sau bua trua",
             {"rest_after_lunch": None, "lunch_required": False}),
            ("PACE_BAND", "khung so diem / nhom loai bat buoc",
             {"min_stops": None, "max_stops": None, "required_any": []}),
            ("MUST_VISIT", "must_visit", {"must_visit": []}),
        )
        for name, label, override in trials:
            probe = optimize(
                stubs, travel, _to_trip(trip), edge_scores=q,
                workers=workers,
                timeout_s=(DIAGNOSE_TIMEOUT_S if deterministic_time is None
                           else DIAGNOSE_WALL_GUARD_S),
                deterministic_time=(None if deterministic_time is None
                                    else DIAGNOSE_DETERMINISTIC_TIME),
                must_visit=override.pop("must_visit", must),
                min_stops=override.pop("min_stops", base_limits["min_stops"]),
                max_stops=override.pop("max_stops", base_limits["max_stops"]),
                required_any=override.pop("required_any",
                                          base_limits["required_any"]),
                rest_after_lunch=override.pop(
                    "rest_after_lunch",
                    base_limits.get("rest_minutes")
                    if base_limits.get("rest_after_lunch") else None),
                late_end_min=base_limits["late_end_min"],
                cafe_cap=override.pop("cafe_cap", cafe_cap),
                no_consecutive=override.pop("no_consecutive", True),
                no_adjacent_food=override.pop("no_adjacent_food", True),
                lunch_required=override.pop(
                    "lunch_required", bool(base_limits.get("lunch_required"))),
                state_bands=state_bands, state_score=state_scores, state_cost=state_costs,
                category_cap=override.pop("category_cap", category_cap),
                max_fee=override.pop("max_fee", _max_fee(trip)))
            if probe.get("itinerary") is not None:
                if name == "BUDGET" and _within_budget(probe, stubs, trip):
                    continue  # it fits the budget: the solver only ran out of time
                culprit = {"rule": name, "label": label}
                if name == "CATEGORY_CAP":
                    # WHICH category needed a second stop? The uncapped probe
                    # shows it: 2+ of one capped category is exactly what the
                    # cap forbids.
                    counts: dict[str, int] = {}
                    for act in probe["itinerary"]["activities"]:
                        cat = soft_rules.poi_category(
                            pois_by_id.get(act["poi_id"], {}))
                        if cat in soft_rules.NON_FOOD_CAPPED:
                            counts[cat] = counts.get(cat, 0) + 1
                    culprit["categories"] = sorted(
                        cat for cat, n in counts.items()
                        if n > soft_rules.CATEGORY_DAILY_CAP)
                return culprit
        return None

    acts = (out.get("itinerary") or {}).get("activities", [])
    # The solver chose the stops; find their shortest legal order and honest times.
    acts = _polished(acts, stubs_used, travel, trip, limits_used, order_prefs, pois_by_id, cells, ctx)
    plan = _assemble(acts, out, trip, pois_by_id, cells, ranked, tpl_name,
                     limits, relaxed_step, cafe_cap, ctx, prof,
                     candidates, travel)
    _add_lean_evidence(plan, leans)
    if rung_used is not None:
        plan["_rung"] = rung_used
    extra = list(date_warnings)
    if acts and stubs_used is short_stubs:
        extra.append("rut ngan thoi gian o cac diem da chon de kip trong khung gio: "
                     + ", ".join(str(pois_by_id[m].get("name")) for m in must))
    if acts and limits.get("dinner_required") and not limits_used.get("dinner_required"):
        extra.append("khong xep duoc bua toi (khong du ngan sach hoac khung gio)")
    misplaced = [a for a in acts if a["poi_id"] not in must_ids
                 and not soft_rules.fits_time_of_day(pois_by_id.get(a["poi_id"]),
                                                     to_min(a["start"]), to_min(a["end"]))]
    extra += [f"{pois_by_id[a['poi_id']].get('name')} xep luc {a['start']} vi day la hoat dong "
              "ban yeu cau, gio nay khong phai luc dep nhat" for a in misplaced]
    if extra:
        plan["warnings"] = extra + list(plan.get("warnings") or [])
    if out.get("itinerary") is None and out.get("status") == "unknown":
        # The budget, not a rule, stopped the search: a rule-by-rule diagnosis
        # would only burn the same budget eight more times.
        plan["infeasible_by"] = {"rule": "SEARCH_BUDGET",
                                 "label": "het ngan sach tim kiem, chua chung minh vo nghiem"}
    elif out.get("itinerary") is None and not distinct_from and diagnose:
        culprit = _diagnose(list(templates.attempts(limits))[-1])
        if culprit:
            plan["infeasible_by"] = culprit
            if culprit["rule"] == "CATEGORY_CAP":
                # Explicit, user-mandated: the cap is NOT weakened; name it
                # (and the category that needed a second stop, when known).
                need = culprit.get("categories") or []
                detail = (f" (can 2 diem loai {', '.join(need)})"
                          if need else "")
                plan.setdefault("warnings", []).insert(0, (
                    "khong xep duoc lich voi pool da xac minh: "
                    f"{culprit['label']}{detail} lam vo nghiem "
                    "(khong tu noi long cap)"))
            else:
                plan.setdefault("warnings", []).insert(0, (
                    f"khong xep duoc lich: {culprit['label']} lam vo nghiem "
                    "(khong tu noi long)"))
    plan["activity_match"] = _activity_match(acts, act_report, pois_by_id)
    warnings = _activity_warnings(plan["activity_match"])
    if warnings:
        plan["warnings"] = list(plan.get("warnings") or []) + warnings
    # Solution pool: every member is a full plan (costs/gate/explanations), so
    # the router can return one directly. A member that fails validation is
    # dropped (defensive: model constraints and gate should agree).
    if pool_size > 1 and out.get("pool"):
        built, dropped = [], 0
        for item in out["pool"]:
            member = _assemble(item["activities"], out, trip, pois_by_id,
                               cells, ranked, tpl_name, limits, relaxed_step,
                               cafe_cap, ctx, prof, candidates, travel)
            if not member.get("passed"):
                dropped += 1
                continue
            _add_lean_evidence(member, leans)
            member["profile"] = profile
            member["activity_match"] = _activity_match(
                item["activities"], act_report, pois_by_id)
            member["_objective"] = float(item.get("objective") or 0.0)
            built.append(member)
        plan["_pool_plans"] = built
        stats = dict(out.get("pool_stats") or {})
        stats["dropped_by_gate"] = dropped
        plan["solution_pool"] = pool_svc.pool_report(
            stats, [{"profile": profile, "poi_ids": item["poi_ids"],
                     "mmr": {"rank": 1, "quality": 1.0, "similarity": 0.0,
                             "score": 1.0}}
                    for item in (out["pool"][:1] if built else [])],
            len(built))
    return plan


def _rest_proof(acts: list[dict], trip: dict, pois_by_id: dict, limits: dict) -> dict | None:
    """The plan's rest window, as the gate must see it (None without a rest lock)."""
    profile_data = trip.get("profile") or {}
    if not (limits.get("rest_after_lunch") and profile_data):
        return None
    span = soft_rules.rest_span(acts, pois_by_id, profile_data, deadline(trip))
    return {"start": hhmm(span["start"]), "end": hhmm(span["end"])} if span else None


def _polished(acts: list[dict], stubs: list, travel: dict, trip: dict, limits: dict,
              order_prefs: list, pois_by_id: dict, cells: dict, ctx: dict | None = None) -> list[dict]:
    """`route_order.best_order` (least driving and dead time), kept only when the gate
    still passes it: the solver's own plan is the fallback for any doubt."""
    if len(acts) < 2:
        return acts
    by_id = {stub.poi_id: stub for stub in stubs}
    # A stop that answers a wish for an hour keeps that hour in any order.
    for group in limits.get("required_any") or []:
        span = group.get("start_between")
        for act in acts if span else []:
            if act["poi_id"] in group["poi_ids"] and span[0] <= to_min(act["start"]) < span[1]:
                by_id[act["poi_id"]] = route_order.held_to(by_id[act["poi_id"]], span)
    # An exposed stop the solver seated in a dry hour stays out of the rain.
    wet = trip_ctx.wet_spans(ctx)
    for act in acts if wet else []:
        start, end = to_min(act["start"]), to_min(act["end"])
        if (trip_ctx.rain_exposure(pois_by_id.get(act["poi_id"])) > 0
                and all(end <= lo or start >= hi for lo, hi in wet)):
            by_id[act["poi_id"]] = route_order.kept_dry(by_id[act["poi_id"]], wet)
    # A place the traveller named is held to its opening hours only, but belongs in
    # the hours it makes sense whenever some order of the day allows that.
    preferred = {}
    for pid in trip.get("must_visit") or []:
        if pid in by_id and soft_rules.time_fit_windows(pois_by_id.get(pid)):
            windows = poi_windows(pois_by_id[pid], trip, deadline(trip))
            if windows != [(0, 0)]:
                preferred[pid] = windows
    better = route_order.best_order(
        acts, by_id, travel, to_min(trip.get("start_time", "07:00")), deadline(trip),
        STOP_OVERHEAD_MIN,
        rest_minutes=limits.get("rest_minutes") if limits.get("rest_after_lunch") else None,
        late_end_min=limits.get("late_end_min"), precedence=order_prefs, preferred=preferred)
    if better is None:
        return acts
    pois_gate = {a["poi_id"]: _gate_view(pois_by_id[a["poi_id"]]) for a in better}
    checked = {"activities": better}
    rest = _rest_proof(better, trip, pois_by_id, limits)
    if rest:
        checked["rest"] = rest
    return better if validate(checked, trip, pois_gate, cells)["passed"] else acts


def _assemble(acts: list[dict], out: dict, trip: dict, pois_by_id: dict,
              cells: dict, ranked: list[dict], tpl_name: str | None,
              limits: dict, relaxed_step: int, cafe_cap: int,
              ctx: dict | None, prof: str, candidates: list[dict],
              travel: dict) -> dict:
    """One activity list -> the full public plan (gate + report + warnings).

    Shared by the argmax plan and every solution-pool member, so a diverse
    response can never show a plan that was not validated the same way.
    """
    # Dynamic state evidence: per-activity state at its planned START, so a
    # client/reviewer can see WHY a stop sits at that hour (satiety, heat,
    # dip). Only an onboarding/state context adds these keys.
    if (ctx or {}).get("dynamic_state"):
        for act in acts:
            act["state"] = trip_ctx.compact_state(ctx, to_min(act["start"]))
    pois_gate = {pid: _gate_view(p) for pid, p in pois_by_id.items()}
    # The plan's rest window is evidence, not a hidden assumption: pass it to
    # the gate so REST_FOLLOWS_LUNCH checks the window the client will see
    # (start within 15 min of lunch end, exact pace length, no POI inside).
    rest_proof = _rest_proof(acts, trip, pois_by_id, limits)
    checked = {"activities": acts}
    if rest_proof:
        checked["rest"] = rest_proof
    rep = validate(checked, trip, pois_gate, cells)

    plan = response.build_plan({**out, "itinerary": {"activities": acts}}, rep,
                               trip, pois_by_id, cells, version=1,
                               itinerary_id="plan")
    plan["reason"] = PROFILE_REASONS[prof]
    plan["scores"] = score_plan(plan)
    plan["diversity"] = plan_diversity(acts, candidates, prof)
    # TASK-2 soft layer: sequence-level A2/B1/B2/E2 report (the edge part of
    # A2/B1 already reached the optimizer through scorer.edge_scores).
    plan["soft_penalties"] = soft_rules.plan_penalties(acts, pois_by_id, trip)
    _attach_explanations(plan, ranked, pois_by_id)
    plan["template"] = _template_report(tpl_name, limits, acts, relaxed_step,
                                       pois_by_id, cafe_cap, trip)
    warnings = []
    if plan.get("cost_estimated"):
        warnings.append("chi phi la uoc tinh theo muc gia, chua phai gia that")
    # FR-026: what the plan assumes about a place, it says.
    stops = [pois_by_id.get(a.get("poi_id")) or {} for a in acts]
    unknown = [p.get("name") for p in stops if p.get("plan_tier") and not p.get("opening_hours")]
    if unknown:
        warnings.append("gio mo cua chua xac minh, nen hoi lai truoc khi di: " + ", ".join(unknown))
    if weekday_of(trip.get("date")) is None:
        for poi in stops:
            days = closed_weekdays(poi)
            if days:
                warnings.append(f"{poi.get('name')} nghi vao "
                                f"{', '.join(WEEKDAY_LABELS[d] for d in days)}: chon ngay di de kiem tra")
    # FR-026: the forecast is part of what the plan assumes. Wet hours are named, with
    # the stops left in the open in them (a wish, a named place, a day with no roof to
    # move under); so is a date the forecast does not reach (each day of a trip its own).
    rain = trip_ctx.rain_note(ctx, acts, pois_by_id)
    if rain:
        warnings.append(rain)
    if (ctx or {}).get("weather_source") == "out_of_range":
        warnings.append(
            f"chua co du bao thoi tiet cho ngay {trip.get('date')} (du bao chi co mot tuan), "
            f"dung nhiet do gia dinh {ctx.get('temp_c')}C (mua coi nhu 0%)")
    on_site = (plan.get("template") or {}).get("lunch_on_site")
    if on_site:
        warnings.append(f"bua trua an tai {(pois_by_id.get(on_site) or {}).get('name') or on_site} "
                        "(diem di ca ngay), khong xep nha hang rieng")
    rest = (plan.get("template") or {}).get("rest_block") or {}
    if rest.get("shrunk"):
        warnings.append(
            f"nghi trua sau bua trua muon ({rest['lunch_end']}) da rut ngan "
            f"con {rest['minutes']} phut (xin {rest['requested_minutes']})")
    if tpl_name and relaxed_step:
        warnings.append(
            f"template {tpl_name}: khong du diem theo khung, da noi long "
            f"bo dem (buoc {relaxed_step})")
    if tpl_name and not candidates:
        warnings.append(f"template {tpl_name}: khong co ung vien phu hop")
    if out.get("itinerary") is None:
        # Fail honestly and loudly: the caps/locks are hard, never silently
        # relaxed, so the caller can see which constraint killed the plan.
        warnings.append(
            f"khong tim duoc lich: {out.get('reason') or 'vo nghiem'} "
            f"(giu nguyen khoa nghi + cap loai + cap cafe + khong trung loai)")

    if warnings:
        plan["warnings"] = warnings
    if (ctx or {}).get("dynamic_state"):
        plan["user_state"] = trip_ctx.plan_report(ctx)
    # T061e: replan context (trip/pois/travel) travels with the stored plan
    # so POST /replan can rebuild the rolling state; the itinerary router
    # strips leading-underscore keys from the public response.
    plan["_context"] = {"trip": trip, "pois": candidates, "travel": travel}
    return plan


def _template_report(name: str | None, limits: dict, acts: list[dict],
                     relaxed_step: int, pois: dict | None = None,
                     cafe_cap: int | None = None,
                     trip: dict | None = None) -> dict:
    """Plan-level evidence: slots, rest window, lunch, stops, relaxation.

    `rest_block` is derived from the plan, not a template constant: its
    `start` is the lunch activity's END and `end` = start + pace length
    (shrunk for a late lunch, floor 20 min; `shrunk` says so). `rest_ok` is
    the locked-window proof (no activity overlaps the siesta). A legacy plan
    (no onboarding profile) reports rest_locked False.
    """
    profile = (trip or {}).get("profile") or {}
    rest, rest_ok = None, None
    rest_locked = bool(limits.get("rest_after_lunch"))
    span = (soft_rules.rest_span(acts, pois or {}, profile,
                                 deadline(trip or {}))
            if rest_locked and profile else None)
    if span:
        rest = {
            "start": hhmm(span["start"]),
            "end": hhmm(span["end"]),
            "minutes": span["minutes"],
            "requested_minutes": span["requested_minutes"],
            "shrunk": span["shrunk"],
            "lunch_end": hhmm(span["lunch_end"]),
            "lunch_poi_id": span["lunch_poi_id"],
            "label": "nghi trua (sau bua trua, theo nhip)",
        }
        lo, hi = span["start"], span["end"]
        rest_ok = all(
            a.get("poi_id") == span["lunch_poi_id"]
            or to_min(a["end"]) <= lo or to_min(a["start"]) >= hi
            for a in acts)
    ordered = sorted(acts, key=lambda a: a.get("start", ""))
    lunch = next(
        (a for a in ordered
         if soft_rules.poi_category((pois or {}).get(a.get("poi_id")))
         == "restaurant"
         and 11 * 60 <= to_min(a["start"]) < 13 * 60),
        None,
    ) if acts else None
    template = templates.DAY_TEMPLATES.get(name) or {}
    # No restaurant lunch on a day that needs one: an all-day stop holds it on site.
    on_site = (soft_rules.lunch_on_site(acts, pois or {})
               if acts and lunch is None and limits.get("lunch_required") else None)
    return {
        "name": name,
        "label": template.get("label", ""),
        "slots": template.get("slots", []),
        "rest_block": rest,
        "rest_locked": rest_locked,
        "rest_ok": rest_ok,
        "lunch_required": bool(limits.get("lunch_required")),
        "lunch_restaurant": lunch,
        "lunch_on_site": on_site.get("poi_id") if on_site else None,
        "cafe_cap": cafe_cap,
        "stops": len(acts),
        "pace_stops": list(template.get("pace_stops", ())),
        "relaxed_step": relaxed_step,
    }


def _add_lean_evidence(plan: dict, leans: dict[str, tuple[float, list[str]]]) -> None:
    """What the profile's soft answers said FOR a stop joins its evidence (FR-023)."""
    for act in plan.get("activities", []):
        evidence = (act.get("explanation") or {}).get("evidence")
        if evidence is None:
            continue
        for reason in leans.get(act.get("poi_id"), (0.0, []))[1]:
            if reason not in evidence:
                evidence.append(reason)


def _attach_explanations(plan: dict, ranked: list[dict], pois_by_id: dict | None = None) -> None:
    """FR-023: every activity carries a grounded explanation (evidence).

    Evidence argues FOR the stop: what the ranker held against it at some hour of
    the day ("nong, tranh ngoai troi" on a beach) is not a reason it was chosen.
    """
    reasons = {r.get("poi_id"): (r.get("reasons") or []) for r in ranked}
    for act in plan.get("activities", []):
        pid = act.get("poi_id")
        poi = (pois_by_id or {}).get(pid) or {}
        evidence = [r for r in reasons.get(pid) or [] if r not in AGAINST_REASONS]
        if not evidence:
            evidence = list(reasons.get(pid) or []) or [f"seed:{pid}"]
        act["explanation"] = {"claim": f"chon {poi.get('name') or pid}", "evidence": evidence,
                              "inference": "", "source": "rank"}
