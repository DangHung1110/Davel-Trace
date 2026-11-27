"""One value per POI for objective v1: T1 of J (`objective.py`), step 4 of the request flow.

    v_i = sum_k w_k * phi_k(i)  +  U0 * sum_m w_m * psi_m(i)

phi, what the place is (the same for every traveller), summed in this order:
    base          1 for every stop
    fee           what one person spends there, per 100k VND, counted double when the
                  whole trip has under 1M; a cost: its weight is subtracted
    rating        trusted rating (`BE.common.trusted_rating`), in stars
    fame          log10(1 + review count); 0 on danang-v2, which has no review counts
    novelty       Vargas novelty inside the pool (`novelty_scores`), 0..1
    free          1 when the entry is known to cost nothing
    free_outdoor  1 when free AND nature / market / park / beach
psi, what the traveller answered at onboarding, in units of U0 = the pool's top phi value
(so 0.20 is a fifth of the best place's value, whatever the profile):
    taste         signed food-pref match (`profile_filter.taste_score`, -1..1)
    spending      +1 / -1: a priced place dearer or cheaper than such places in the pool
                  usually are, times the side the spending level asks for
    outdoor       outdoor_bias (-1..1) on an open-air place (`soft_rules.is_outdoor`)
    liked         1 when the place answers a liked activity (`retrieval.poi_is_liked`)

The weights are the `value` block of the objective's weights file; a profile overrides
single keys in `profiles.<name>.value` (`objective.value_weights`), so savings, balanced
and experience are this one function under three weight sets. Nothing here reads a
profile name. With the pre-v1 node-score constants as weights the values are
bit-identical to `profiles._score` + taste + lean (pinned in test_value_function), except
savings, which no longer charges its mean matrix leg here (riding minutes are T9's) nor a
price level: on danang-v2 the level is the price tier again, the very source of `fee`
(medium = level 2 in 371/371, expensive = level 3 in 16/16), so it only charged a priced
place ~6% more and two collinear columns cannot be told apart when the weights are learned
(dropped 26/11: 52 of 60 savings days kept their stops).
`cap_avg_leg` is not part of v_i: the candidate cap (step 6) ranks by
v_i - cap_avg_leg * the POI's mean leg, the savings prior that keeps a compact cluster
among its 40 candidates.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from BE.app.services import profile_filter, retrieval, soft_rules
from BE.common import (
    FEW_REVIEWS, clamp01, effective_fee, price_level_of, to_float, to_int, trusted_rating)

# phi in summing order (the order keeps the float sums equal to the pre-v1 formulas).
PLACE = ("base", "fee", "rating", "fame", "novelty", "free", "free_outdoor")
PERSON = ("taste", "spending", "outdoor", "liked")
COSTS = frozenset({"fee"})
# Not a term of v_i: the cap's weight on the mean matrix leg (step 6).
CAP_KEYS = ("cap_avg_leg",)

FEE_UNIT_VND = 100_000
TIGHT_BUDGET_VND = 1_000_000      # under this, every fee VND counts double
TIGHT_FEE_MULTIPLIER = 2.0
FREE_OUTDOOR_CATEGORIES = frozenset({"nature", "market", "park", "beach"})

# Vargas novelty: a POI below the fit floor is not "novel", it is just poorly rated.
NOVELTY_FIT_FLOOR = 3.0           # 3.0 -> fit 0.0
NOVELTY_FIT_SPAN = 1.9            # 4.9 -> fit 1.0
# Explanations: when a component speaks FOR a stop.
NOVEL_REASON = 0.30               # profiles.plan_diversity counts a stop novel from here
HIGH_RATING = 4.5
CHEAP_FEE_VND = 50_000
KNOWN_REVIEWS = 1_000


def novelty_scores(pois: list[dict]) -> dict[str, float]:
    """Vargas-style novelty in [0, 1] for every POI in a candidate pool.

    novelty = fit * (0.55 * (1 - popularity) + 0.30 * category-rarity
                     + 0.15 * tag-rarity)

    - fit: rating above NOVELTY_FIT_FLOOR, normalised (3.0 -> 0, 4.9 -> 1).
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
        fit = clamp01((rating - NOVELTY_FIT_FLOOR) / NOVELTY_FIT_SPAN)
        popularity = ((rating - lo) / (hi - lo)) if hi > lo else 0.5
        if p.get("must_go"):
            popularity = min(1.0, popularity + 0.25)
        cat_rarity = (1.0 - math.sqrt(cats[cat] / n)) if cat else 0.0
        novelty = fit * (0.55 * (1.0 - popularity)
                         + 0.30 * cat_rarity
                         + 0.15 * _tag_rarity(p))
        out[p["poi_id"]] = round(clamp01(novelty), 4)
    return out


def price_reference(pois: list[dict]) -> dict[str, int]:
    """What a priced place usually costs in this pool: the median price level of
    each priced category (restaurants 2, cafes 1 on danang-v1). The spending lean reads
    a place against it, so "cheap" means cheap for a restaurant, not cheaper than a park."""
    levels: dict[str, list[int]] = {}
    for poi in pois:
        cat = soft_rules.poi_category(poi)
        if cat in retrieval.PAID_CATS:
            levels.setdefault(cat, []).append(price_level_of(poi))
    return {cat: sorted(values)[len(values) // 2] for cat, values in levels.items()}


def lean_parts(poi: dict, profile: dict | None, liked: list[str] | None = None,
               price_ref: dict[str, int] | None = None) -> tuple[dict[str, float], list[str]]:
    """The onboarding's soft answers for one POI: (psi spending / outdoor / liked, reasons).

    Each part is signed and 0 for the neutral answer (spending level 2, bias 0, nothing
    ticked), so a profile that says nothing gives zeros. The reasons are those that speak
    FOR the stop (a lean against it is no evidence). `liked`:
    `retrieval.liked_wishes(profile["activities"])`; `price_ref`: `price_reference(pool)`.
    """
    profile = profile or {}
    parts = {"spending": 0.0, "outdoor": 0.0, "liked": 0.0}
    reasons: list[str] = []
    cat = soft_rules.poi_category(poi)
    wants = to_int(profile.get("spending_level"), 2) - 2          # -1 thrifty .. +1 premium
    if wants and cat in retrieval.PAID_CATS:
        dearer = max(-1, min(1, price_level_of(poi) - (price_ref or {}).get(cat, 2)))
        parts["spending"] = wants * dearer
        if wants * dearer > 0:
            reasons.append("hop muc chi tieu")
    bias = max(-1.0, min(1.0, to_float(profile.get("outdoor_bias"))))
    if bias and soft_rules.is_outdoor(poi):
        parts["outdoor"] = bias
        if bias > 0:
            reasons.append("hop gu ngoai troi")
    if liked and retrieval.poi_is_liked(poi, liked):
        parts["liked"] = 1.0
        reasons.append("hop hoat dong ban thich")
    return parts, reasons


def taste_prefs(trip: dict) -> list[str]:
    """The food prefs a trip plans with: the onboarding's, else the trip's; a food wish
    phrased as an activity ("ăn hải sản") is a taste pref too."""
    profile = trip.get("profile") or {}
    prefs = list(profile.get("food_prefs") or []) or list(trip.get("food_prefs") or [])
    for activity in trip.get("activities") or []:
        prefs += [t for t in profile_filter.cuisine_terms(activity) if t not in prefs]
    return prefs


@dataclass(frozen=True)
class Pool:
    """What the features read off one request, computed once per candidate pool."""
    novelty: dict
    price_ref: dict
    prefs: tuple
    liked: tuple
    profile: dict
    budget: float | None


def pool_of(pois: list[dict], trip: dict) -> Pool:
    profile = trip.get("profile") or {}
    return Pool(novelty=novelty_scores(pois), price_ref=price_reference(pois),
                prefs=tuple(taste_prefs(trip)),
                liked=tuple(retrieval.liked_wishes(profile.get("activities"))),
                profile=profile, budget=trip.get("budget"))


def place_features(poi: dict, pool: Pool) -> dict[str, float]:
    """phi of one POI (module docstring); the same for every profile."""
    known_fee = effective_fee(poi)
    fee_unit = FEE_UNIT_VND
    if pool.budget is not None and 0 < float(pool.budget) < TIGHT_BUDGET_VND:
        fee_unit = fee_unit / TIGHT_FEE_MULTIPLIER
    free = known_fee == 0
    return {
        "base": 1.0,
        "fee": (known_fee or 0) / fee_unit,
        "rating": trusted_rating(poi),
        "fame": math.log10(1 + int(poi.get("review_count") or 0)),
        "novelty": float(pool.novelty.get(poi.get("poi_id"), 0.0)),
        "free": 1.0 if free else 0.0,
        "free_outdoor": 1.0 if free and soft_rules.poi_category(poi) in FREE_OUTDOOR_CATEGORIES
        else 0.0,
    }


def place_value(phi: dict[str, float], w: dict) -> float:
    """sum_k w_k phi_k, costs subtracted, in PLACE order, rounded like the pre-v1 scores."""
    total = 0.0
    for key in PLACE:
        weight = float(w.get(key, 0.0))
        if key in COSTS:
            total -= weight * phi[key]
        else:
            total += weight * phi[key]
    return round(total, 4)


@dataclass(frozen=True)
class Scored:
    """v_i of a pool under one weight set."""
    values: dict          # poi_id -> v_i
    unit: float           # U0: the top place value of the pool
    reasons: dict         # poi_id -> what speaks FOR the stop, under these weights


def score(pois: list[dict], trip: dict, w: dict) -> Scored:
    """v_i of every POI of `pois` (the request's candidate pool) under value weights `w`."""
    pool = pool_of(pois, trip)
    phis = {p["poi_id"]: place_features(p, pool) for p in pois}
    places = {pid: place_value(phi, w) for pid, phi in phis.items()}
    unit = max(places.values(), default=1.0)
    if unit <= 0:
        unit = 1.0
    w_taste = float(w.get("taste", 0.0))
    values, reasons = {}, {}
    for p in pois:
        pid = p["poi_id"]
        taste, hits, _clashes = profile_filter.taste_score(p, list(pool.prefs))
        parts, _lean_reasons = lean_parts(p, pool.profile, list(pool.liked), pool.price_ref)
        lean = 0.0
        for key in ("spending", "outdoor", "liked"):
            lean += float(w.get(key, 0.0)) * parts[key]
        values[pid] = places[pid] + w_taste * unit * taste + unit * round(lean, 4)
        reasons[pid] = explain(p, phis[pid], w, taste, hits, parts)
    return Scored(values=values, unit=unit, reasons=reasons)


def explain(poi: dict, phi: dict, w: dict, taste: float, hits: list[str],
            parts: dict) -> list[str]:
    """The components that raised v_i under these weights, in words (FR-023 evidence).

    A component counts only when its weight is on: savings says "mien phi", balanced
    the rating, experience the novelty, every profile the traveller's own answers.
    """
    out: list[str] = []
    on = {key: float(w.get(key, 0.0)) > 0 for key in (*PLACE, *PERSON)}
    rating = float(poi.get("rating") or 0.0)
    reviews = poi.get("review_count")
    if on["rating"] and rating >= HIGH_RATING and (reviews is None or reviews >= FEW_REVIEWS):
        out.append(f"rating cao {rating}")
    if on["fame"] and int(reviews or 0) >= KNOWN_REVIEWS:
        out.append(f"nhieu nguoi biet ({int(reviews)} danh gia)")
    if on["novelty"] and phi["novelty"] >= NOVEL_REASON:
        out.append("doc dao, it nguoi biet")
    fee = effective_fee(poi)
    if on["free"] or on["fee"]:
        if phi["free"]:
            out.append("mien phi")
        elif on["fee"] and fee is not None and fee <= CHEAP_FEE_VND:
            out.append(f"re ({fee // 1000}k/nguoi)")
    if on["taste"] and taste > 0:
        out.append("dung gu an: " + ", ".join(hits))
    for key, reason in (("spending", "hop muc chi tieu"), ("outdoor", "hop gu ngoai troi"),
                        ("liked", "hop hoat dong ban thich")):
        if on[key] and parts[key] > 0:
            out.append(reason)
    return out
