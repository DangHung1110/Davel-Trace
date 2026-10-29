"""Multi-profile optimizer runs + solution pool (T032, lane B; US4).

Three profiles are STRUCTURALLY DIFFERENT objectives over the same candidate
pool and the same hard gates (habitability: lunch/rest/caps/adjacency apply to
every option, so every profile stays a plan a human can actually do):

- savings  -> COST-FIRST: minimise fee + travel (avg matrix leg), reward
              free/nature/market stops, respect a tight budget harder.
- balanced -> RATING-FIRST: maximise the rating sum (the previous behaviour).
- experience -> NOVELTY-FIRST: Vargas-style novelty (low popularity, rare
              category/tag, high fit) + a dominant category-spread term, so
              the day is composed of POIs the rating-first plan skips.

`/v1/itinerary` now returns all three by default; the router additionally
enforces a pairwise POI-set Jaccard ceiling (see `pool.enforce_pairwise`) so
the three options are genuinely different days, not three reorderings.

Each run -> validate (T018) -> score (total cost, travel time,
preference = mean rating) + profile reason + T032s `scores`
(profit/utility/gate/excluded) + a `diversity` report. Infeasible runs are
dropped with a note (never returned). `selected: None` stays the contract
stub (select endpoint is lane C T033e).
"""

from __future__ import annotations

import math
from collections import Counter

from BE.app.services import (
    pool as pool_svc,
    profile_filter,
    response,
    retrieval,
    scorer,
    soft_rules,
    templates,
    trip_ctx,
)
from BE.app.services.common import hh, status_map, to_min, total_fee
from BE.app.services.gate import SOFT_CHECKS
from BE.app.services.optimizer import (
    POOL_DEFAULT_BAND, StubTrip, optimize, stubs_from_pois)
from BE.app.services.validator import validate

PROFILE_REASONS = {
    "savings": "tiết kiệm: chi phí + di chuyển thấp nhất, ưu tiên điểm "
               "miễn phí/thiên nhiên/chợ",
    "balanced": "cân bằng: tổng rating cao nhất trong ràng buộc",
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
TIGHT_BUDGET_VND = 1_000_000      # under this, every fee VND counts double
SAVINGS_TIGHT_FEE_MULTIPLIER = 2.0

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

# Category-spread strength per profile (optimizer TASK-1 term). Experience
# makes it dominant: a new category is worth more than another restaurant.
DIVERSITY_WEIGHT_BY_PROFILE = {
    "savings": 1.0,
    "balanced": 1.0,
    "experience": 2.5,
}

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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


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
    ratings = [float(p.get("rating") or 0.0) for p in pool]
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
        rating = float(p.get("rating") or 0.0)
        fit = _clamp01((rating - EXPERIENCE_FIT_FLOOR) / EXPERIENCE_FIT_SPAN)
        popularity = ((rating - lo) / (hi - lo)) if hi > lo else 0.5
        if p.get("must_go"):
            popularity = min(1.0, popularity + 0.25)
        cat_rarity = (1.0 - math.sqrt(cats[cat] / n)) if cat else 0.0
        novelty = fit * (0.55 * (1.0 - popularity)
                         + 0.30 * cat_rarity
                         + 0.15 * _tag_rarity(p))
        out[p["poi_id"]] = round(_clamp01(novelty), 4)
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

    Savings subtracts the matrix leg time from q_ij, so the solver minimises
    the real tour (fee is handled at the node level). Other profiles keep the
    learned/rule transition score unchanged.
    """
    if profile != "savings":
        return q
    return {(a, b): round(value - travel.get((a, b), 0)
                          * SAVINGS_EDGE_TRAVEL_WEIGHT, 4)
            for (a, b), value in q.items()}


def _score(profile: str, p: dict, novelty: dict[str, float] | None = None,
           avg_leg: float = 0.0, budget: float | None = None) -> float:
    """Node score for one profile (see module docstring).

    savings: absolute cost minimisation (fee + travel), not a tie-break.
    balanced: the previous rating sum, constraints respected.
    experience: novelty-first with a dominant category-spread term in the
    optimizer (`DIVERSITY_WEIGHT_BY_PROFILE`); the node score itself is
    novelty + a small rating/fit term.
    """
    rating, fee = float(p.get("rating") or 0), int(p.get("fee") or 0)
    if profile == "savings":
        cat = soft_rules.poi_category(p)
        price_level = int(p.get("price_level") or 1)
        fee_weight = SAVINGS_FEE_UNIT
        if budget is not None and 0 < float(budget) < TIGHT_BUDGET_VND:
            fee_weight = fee_weight / SAVINGS_TIGHT_FEE_MULTIPLIER
        score = SAVINGS_BASE - (fee / fee_weight)
        score -= avg_leg * SAVINGS_TRAVEL_WEIGHT
        score -= max(0, price_level - 1) * SAVINGS_PRICE_LEVEL_PENALTY
        score += rating * SAVINGS_RATING_WEIGHT
        if fee == 0:
            score += SAVINGS_FREE_BONUS
            if cat in SAVINGS_CATEGORIES:
                score += SAVINGS_CHEAP_CATEGORY_BONUS
        return round(score, 4)
    if profile == "experience":
        nov = float((novelty or {}).get(p.get("poi_id"), 0.0))
        return round(rating * EXPERIENCE_RATING_WEIGHT
                     + nov * EXPERIENCE_NOVELTY_WEIGHT, 4)
    return rating  # balanced: rating-first


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


def run_profiles(pois: list[dict], travel: dict[tuple[str, str], int],
                 trip: dict, matrix: dict,
                 profiles: tuple[str, ...] = ("savings", "balanced",
                                              "experience")) -> dict:
    """Run each profile; return {"plans": [...], "dropped": [...], "selected": None}.

    Each plan entry carries its T032s `scores` (profit/utility/gate/
    excluded) attached once the entry is complete.
    """
    plans, dropped = [], []
    by_id = {p["poi_id"]: p for p in pois}
    ids = [p["poi_id"] for p in pois]
    nov = novelty_scores(pois)
    budget = trip.get("budget")
    q_all = scorer.edge_scores(ids, by_id)
    # Universal human needs apply whenever the request carries an onboarding
    # profile (same seam as build_plan); a profile-less eval baseline stays
    # legacy. The rest window follows the lunch activity's end.
    limits = (templates.universal_constraints(trip)
              if trip.get("profile") else templates.NO_LIMITS)
    rest_after_lunch = (limits.get("rest_minutes")
                        if limits.get("rest_after_lunch") else None)
    pois_gate = {pid: _gate_view(p) for pid, p in by_id.items()}
    for prof in profiles:
        stub = stubs_from_pois(
            pois, trip,
            lambda p: _score(prof, p, novelty=nov,
                             avg_leg=_avg_leg(travel, p["poi_id"], ids),
                             budget=budget))
        out = optimize(stub, travel, _to_trip(trip),
                       edge_scores=_profile_edges(prof, q_all, travel),
                       must_visit=trip.get("must_visit", []),
                       # Same hard caps the gate enforces (eval path parity).
                       cafe_cap=soft_rules.cafe_cap(trip.get("profile")),
                       no_consecutive=True, no_adjacent_food=True,
                       lunch_required=bool(limits.get("lunch_required")),
                       rest_after_lunch=rest_after_lunch,
                       category_cap=soft_rules.CATEGORY_DAILY_CAP,
                       diversity_weight=DIVERSITY_WEIGHT_BY_PROFILE.get(prof))
        if out["itinerary"] is None:
            dropped.append({"profile": prof, "reason": out.get("reason", "")})
            continue
        acts = out["itinerary"]["activities"]
        checked = {"activities": acts}
        if rest_after_lunch and trip.get("profile"):
            span = soft_rules.rest_span(acts, by_id, trip["profile"],
                                        _deadline(trip))
            if span:
                checked["rest"] = {"start": hh(span["start"]),
                                   "end": hh(span["end"])}
        rep = validate(checked, trip, pois_gate, matrix)
        if not rep["passed"]:
            dropped.append({"profile": prof, "reason": str(rep["violations"])})
            continue
        ratings = [float(by_id[a["poi_id"]].get("rating") or 0) for a in acts]
        travel_min = sum(int((matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {})
                             .get("minutes", 0)) for x, y in zip(acts, acts[1:]))
        entry = {
            "profile": prof,
            "reason": PROFILE_REASONS[prof],
            "itinerary": {"activities": acts},
            "total_cost": total_fee(acts, by_id),
            "travel_min": travel_min,
            "preference": round(sum(ratings) / len(ratings), 3) if ratings else 0.0,
            "constraint_status": status_map(
                {name: ok for name, ok in rep["checks"].items()
                 if name not in SOFT_CHECKS}),
            "soft_violations": rep.get("soft_violations", []),
        }
        entry["diversity"] = plan_diversity(acts, pois, prof)
        entry["scores"] = score_plan(entry)  # T032s: attached once complete
        plans.append(entry)
    return {"plans": plans, "dropped": dropped, "selected": None}


def _to_trip(trip: dict, origin_id: str | None = "depot") -> StubTrip:
    return StubTrip(to_min(trip.get("start_time", "07:00")),
                    _deadline(trip), origin_id)


def _deadline(trip: dict) -> int:
    """ETB hard within-day deadline: min(end_time, return_time)."""
    end = to_min(trip.get("end_time", "18:00"))
    rt = trip.get("return_time")
    return min(end, to_min(rt)) if rt else end


def _ladder(limits: dict, act_groups: list[dict]) -> list[tuple[int, dict]]:
    """Template ladder with the trip's activity groups riding along.

    The user's own wishes outrank the template's inferred counts: every
    template rung is tried WITH the activity groups first, and only when none
    fits are the wishes dropped (the plan then reports them as unmet).
    Returns (template_step, limits) pairs so `relaxed_step` keeps its meaning;
    a rung identical to an earlier one (legacy NO_LIMITS) is not re-solved.
    """
    plain = list(enumerate(templates.attempts(limits)))
    wished = [(step, {**rung, "required_any": list(rung["required_any"]) + act_groups})
              for step, rung in plain] if act_groups else []
    out: list[tuple[int, dict]] = []
    for step, rung in wished + plain:
        if all(rung != seen for _, seen in out):
            out.append((step, rung))
    return out


def _activity_match(acts: list[dict], report: list[dict],
                    pois_by_id: dict) -> list[dict]:
    """Per-activity outcome on THIS plan: "required" becomes met/unmet."""
    cats = {soft_rules.poi_category(pois_by_id.get(a.get("poi_id"), {}))
            for a in acts}
    out = []
    for entry in report:
        entry = dict(entry)
        if entry["status"] == "required":
            entry["status"] = ("met" if cats & set(entry["categories"])
                               else "unmet")
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
        elif entry["status"] == "no_verified_poi":
            lines.append(f"chua co diem {cats} da xac minh cho hoat dong "
                         f"'{entry['activity']}'")
        elif entry["status"] == "not_understood":
            lines.append(f"chua hieu hoat dong '{entry['activity']}', bo qua")
    return lines


# What the gate registry reads off a POI: FAR/BCS/VROH, the category for
# A1/caps, and the PROFILE_SAFE haystack (tags/cuisine/ambience/smart_tags/
# intensity, the same fields profile_filter.hard_filter matched).
_GATE_EXTRA = ("tags", "cuisine", "ambience", "smart_tags", "intensity")


def _gate_view(p: dict) -> dict:
    view = {"verified": p.get("verified", False), "fee": p.get("fee", 0),
            "opening_hours": p.get("opening_hours", []),
            "type": p.get("type", ""), "cat": p.get("cat", "")}
    view.update({k: p[k] for k in _GATE_EXTRA if k in p})
    return view


def _travel_from_cells(cells: dict, ids: list[str]) -> dict:
    """T061a: matrix cells -> {(a,b): minutes}; a missing cell stays ABSENT (B3)."""
    travel = {}
    for a in ids:
        for b in ids:
            if a == b:
                continue
            cell = cells.get(f"{a}->{b}")
            if cell is not None:
                travel[(a, b)] = int(cell["minutes"])
    return travel


def build_plan(profile: str, trip: dict, ranked: list[dict],
               pois_by_id: dict, cells: dict, workers: int = 0,
               template: str | None = None, ctx: dict | None = None,
               pool_size: int = 1,
               pool_band: float = POOL_DEFAULT_BAND,
               pool_timeout_s: float | None = None,
               timeout_s: float | None = None,
               deterministic_time: float | None = None) -> dict:
    """T020/T032 router seam: one profile -> one real plan dict.

    Called by POST /v1/itinerary. Adapts the ranked candidate POIs (T061a),
    runs the T017 optimizer as an OPEN tour (no depot cell in the seed
    matrix — see optimizer T061a note), validates (T018) and shapes the
    response (T019) with per-activity explanations (T042).

    Onboarding wiring (profile templates):
    - `template` may be passed explicitly by the router (one of the three
      names, or "" for a legacy request). When it is None, a template is
      derived from `trip["profile"]` only if that profile is present — so the
      eval baselines and older callers keep the exact previous behaviour.
    - A template's hard bans (allowed categories, intensity ceiling) filter
      the candidate list BEFORE the solver, and its pace band / required
      categories / locked rest window / late end constrain the model. A small
      pool relaxes stop-count/required counts (reported), never the bans.
    - `food_prefs` add a SIGNED additive taste bonus to each optimizer node
      score (see TASTE_WEIGHT and profile_filter.taste_score): +1 for a full
      match, -1 for an exclusive cuisine clash, 0 for a non-food POI. It is
      large enough to beat a ~0.4 rating gap, so taste wins a slot against a
      higher-rated mismatch instead of only re-ordering the rank list.
    - `ctx` (trip_ctx.build, optional) turns on the DYNAMIC STATE soft layer:
      the transition scorer gets the satiety-aware food penalty and the
      CP-SAT objective gets per-band state multipliers, so a beach is not
      placed in the 14:00 dip and a restaurant is not stacked right after
      lunch. It also attaches `user_state` evidence and per-activity state
      to the plan. Passing no ctx keeps the exact previous planning output.
    - Universal human needs are solver constraints for EVERY profile (and for
      a custom profile with no archetype): exactly one lunch restaurant in
      11:00-13:00, a rest window STARTING at that lunch's END (60/45/30 min by
      pace, shrunk to fit a late lunch with a 20-min floor), at most one
      dinner restaurant (gate A1), the cafe quota (gate CAFE_CAP), at most ONE
      non-food POI per category per day (gate CATEGORY_CAP), no consecutive
      same-category stops (NO_CONSECUTIVE) and no adjacent restaurants of any
      cuisine (NO_ADJACENT_FOOD).
      These never relax: an infeasible pool returns an honest empty plan plus
      a warning naming the constraint, never a silently broken schedule.
    - `pool_size` (>1) asks the optimizer for a solution pool inside
      `pool_band` * OPT; every member is built into a full plan and attached
      privately as `_pool_plans` (the router's diverse mode MMR-selects from
      it, and the default-mode Jaccard guarantee lazily refills from it).
      `pool_timeout_s` caps the enumeration; `solution_pool` on the public
      plan carries the enumeration stats.
    - `timeout_s` / `deterministic_time` are forwarded to CP-SAT. The eval
      harness passes a deterministic budget so a published comparison is
      reproducible; the endpoint keeps the wall-clock default.

    The endpoint still owns `itinerary_id`/`trip_id`/`profile`; this returns
    the plan body those fields are attached to. `workers` is forwarded to
    CP-SAT (0 = default; 1 = deterministic, used by the T053 harness).
    """
    prof = profile if profile in PROFILE_REASONS else "balanced"
    tpl_name = template
    if tpl_name is None:  # direct callers: derive only from an explicit profile
        tpl_name = (templates.select_template(trip["profile"])
                    if trip.get("profile") else "")
    if tpl_name not in templates.DAY_TEMPLATES:
        tpl_name = None  # "" / unknown / no profile -> legacy (no archetype)
    # A custom profile with no archetype still gets the universal lunch + rest
    # lock; a request with no profile at all stays fully legacy.
    limits = (templates.template_constraints(tpl_name, trip) if tpl_name
              else templates.universal_constraints(trip))

    # Fail closed: the pool is exactly the ranked (verified, hard-filtered)
    # candidates. An empty pool is an honest empty plan, never "every POI"
    # (that fallback re-admitted unverified and allergy-dropped POIs).
    ranked_ids = [r.get("poi_id") for r in ranked]
    candidates = [pois_by_id[pid] for pid in ranked_ids if pid in pois_by_id]

    # Template hard bans: nightlife/spa for a family day, trek for a calm one.
    if tpl_name:
        candidates = [p for p in candidates if templates.allows(p, tpl_name)]
    ids = [p["poi_id"] for p in candidates]

    # Activities -> "at least one stop of these categories" (FR-006: a
    # preference the ladder may relax with a warning, never a pool filter).
    act_groups, act_report = retrieval.activity_requirements(
        trip.get("activities") or [], candidates)

    if not candidates:
        plan = _assemble([], {"itinerary": None,
                              "reason": "khong co POI da xac minh nao qua bo loc"},
                         trip, pois_by_id, cells, ranked, tpl_name, limits, 0,
                         soft_rules.cafe_cap(trip.get("profile") or {}), ctx,
                         prof, candidates, {})
        plan["infeasible_by"] = {"rule": "EMPTY_POOL",
                                 "label": "pool rong sau bo loc cung"}
        plan["activity_match"] = act_report
        plan["warnings"] = (list(plan.get("warnings") or [])
                            + _activity_warnings(act_report))
        return plan

    travel = _travel_from_cells(cells, ids)
    profile_data = trip.get("profile") or {}
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

    def _score_with_taste(poi: dict) -> float:
        unit_delta, _hits, _clashes = profile_filter.taste_score(poi, prefs)
        return base_scores[poi["poi_id"]] + TASTE_WEIGHT * unit * unit_delta

    stubs = stubs_from_pois(candidates, trip, _score_with_taste,
                            deadline=_deadline(trip))
    q = _profile_edges(prof, scorer.edge_scores(ids, pois_by_id, ctx=ctx),
                       travel)
    # Dynamic state: same per-band multipliers the ranker scores against,
    # but here the solver chooses the band the stop lands in.
    state_bands, state_scores = ((None, None)
                                 if not (ctx or {}).get("dynamic_state")
                                 else trip_ctx.optimizer_state(ctx, candidates))
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
    solver_opts = {}
    if timeout_s is not None:
        solver_opts["timeout_s"] = float(timeout_s)
    if deterministic_time is not None:
        solver_opts["deterministic_time"] = float(deterministic_time)
    for step, limits_try in _ladder(limits, act_groups):
        out = optimize(stubs, travel, _to_trip(trip, origin_id=None),
                       edge_scores=q, workers=workers, must_visit=must,
                       min_stops=limits_try["min_stops"],
                       max_stops=limits_try["max_stops"],
                       required_any=limits_try["required_any"],
                       blocked_window=limits_try["blocked_window"],
                       rest_after_lunch=(limits_try.get("rest_minutes")
                                         if limits_try.get(
                                             "rest_after_lunch") else None),
                       late_end_min=limits_try["late_end_min"],
                       cafe_cap=cafe_cap, no_consecutive=True,
                       no_adjacent_food=True,
                       lunch_required=bool(limits_try.get("lunch_required")),
                       state_bands=state_bands,
                       state_score=state_scores,
                       category_cap=category_cap,
                       diversity_weight=DIVERSITY_WEIGHT_BY_PROFILE.get(prof),
                       solution_pool=pool_size, pool_band=pool_band,
                       pool_timeout_s=pool_timeout_s,
                       **solver_opts)
        if out.get("itinerary") is not None:
            relaxed_step = step
            break

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
                stubs, travel, _to_trip(trip, origin_id=None), edge_scores=q,
                workers=workers, timeout_s=2.0,
                must_visit=override.pop("must_visit", must),
                min_stops=override.pop("min_stops", base_limits["min_stops"]),
                max_stops=override.pop("max_stops", base_limits["max_stops"]),
                required_any=override.pop("required_any",
                                          base_limits["required_any"]),
                blocked_window=base_limits["blocked_window"],
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
                state_bands=state_bands, state_score=state_scores,
                category_cap=override.pop("category_cap", category_cap))
            if probe.get("itinerary") is not None:
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
    plan = _assemble(acts, out, trip, pois_by_id, cells, ranked, tpl_name,
                     limits, relaxed_step, cafe_cap, ctx, prof,
                     candidates, travel)
    if out.get("itinerary") is None:
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


def _assemble(acts: list[dict], out: dict, trip: dict, pois_by_id: dict,
              cells: dict, ranked: list[dict], tpl_name: str | None,
              limits: dict, relaxed_step: int, cafe_cap: int,
              ctx: dict | None, prof: str, candidates: list[dict],
              travel: dict) -> dict:
    """One activity list -> the full public plan (gate + report + warnings).

    Shared by the argmax plan and every solution-pool member, so a diverse
    response can never show a plan that was not validated the same way.
    """
    profile_data = trip.get("profile") or {}
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
    rest_proof = None
    if limits.get("rest_after_lunch") and profile_data:
        span = soft_rules.rest_span(acts, pois_by_id, profile_data,
                                    _deadline(trip))
        if span:
            rest_proof = {"start": hh(span["start"]), "end": hh(span["end"])}
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
    _attach_explanations(plan, ranked)
    plan["template"] = _template_report(tpl_name, limits, acts, relaxed_step,
                                       pois_by_id, cafe_cap, trip)
    warnings = []
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
                                 _deadline(trip or {}))
            if rest_locked and profile else None)
    if span:
        rest = {
            "start": hh(span["start"]),
            "end": hh(span["end"]),
            "minutes": span["minutes"],
            "requested_minutes": span["requested_minutes"],
            "shrunk": span["shrunk"],
            "lunch_end": hh(span["lunch_end"]),
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
    if name is None:
        return {"name": None, "label": "", "slots": [], "rest_block": rest,
                "rest_locked": rest_locked, "rest_ok": rest_ok,
                "lunch_required": bool(limits.get("lunch_required")),
                "lunch_restaurant": lunch,
                "cafe_cap": cafe_cap,
                "stops": len(acts), "pace_stops": [],
                "relaxed_step": relaxed_step}
    template = templates.DAY_TEMPLATES[name]
    return {
        "name": name,
        "label": template["label"],
        "slots": template["slots"],
        "rest_block": rest,
        "rest_locked": rest_locked,
        "rest_ok": rest_ok,
        "lunch_required": bool(limits.get("lunch_required")),
        "lunch_restaurant": lunch,
        "cafe_cap": cafe_cap,
        "stops": len(acts),
        "pace_stops": list(template["pace_stops"]),
        "relaxed_step": relaxed_step,
    }


def _attach_explanations(plan: dict, ranked: list[dict]) -> None:
    """FR-023: every activity carries a grounded explanation (evidence)."""
    reasons = {r.get("poi_id"): (r.get("reasons") or []) for r in ranked}
    for act in plan.get("activities", []):
        pid = act.get("poi_id")
        evidence = list(reasons.get(pid) or []) or [f"seed:{pid}"]
        act["explanation"] = {"claim": f"chon {pid}", "evidence": evidence,
                              "inference": "", "source": "rank"}
