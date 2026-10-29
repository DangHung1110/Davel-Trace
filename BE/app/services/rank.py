"""Rule ranker nac-1 (T016, lane C). Attribute + context weights.

score_poi(poi, user, ctx) -> {"score": 0..1, "reasons": [...]}.
WEIGHTS sum to 1, all non-negative (unit test enforces sanity).
PATM nac-2 (T029 model) replaces these weights later; the reasons
format stays (explainer T042 reuses it).

Signals:
- attr: rating/5, price fit (fee share of budget), effort fit
  (intensity vs fitness), weather-safe base.
- ctx: keyword match user prefs vs tags/type/cuisine/ambience,
  time-of-day (evening prefers food/landmark, midday avoids outdoor),
  rain penalizes weather_sensitive POIs.
- taste (own component, weight 0.18): the onboarding food_prefs. It answers
  "does this place serve what I want to eat", which the keyword `pref_match`
  cannot: it is additive, so a 4.5 seafood place beats a 4.9 BBQ joint for a
  seafood profile (0.4 rating = 0.4/5 * 0.22 = 0.0176 in rank units, a full
  taste hit is 0.18 * 0.5 = 0.09), and an exclusive clash (vegan-only venue
  for a BBQ lover) subtracts the same amount.
- state (trip_ctx): when the ctx carries `dynamic_state` (onboarding
  profile), the score is evaluated at each hour of the trip and multiplied
  by the traveler state at that hour (satiety / fatigue / heat / dip /
  evening). The final score is the MEAN over the trip hours, which is what
  "how well does this POI fit the whole day" means; the optimizer then
  chooses the actual hour with the per-band state bonus
  (trip_ctx.optimizer_state). Without a profile the legacy single-hour
  score is returned unchanged.
"""

from __future__ import annotations

from BE.app.services import to_min
from BE.app.services import profile_filter, trip_ctx
from BE.app.services.soft_rules import NIGHT_START, NIGHT_TYPES, poi_category
from BE.common import price_level_of

WEIGHTS = {
    "rating": 0.22,
    "price": 0.12,
    "effort": 0.10,
    "pref_match": 0.16,
    "taste": 0.18,
    "time_fit": 0.10,
    "weather": 0.12,
}

# Taste component mapping: the signed unit from profile_filter.taste_score
# (-1 clash .. +1 full match) lands on [0, 1] around the neutral 0.5, so a
# food POI with no cuisine evidence is neither rewarded nor punished.
TASTE_NEUTRAL = 0.5

# Categories the onboarding `outdoor_bias` moves (beach/nature/park/viewpoint).
OUTDOOR_CATEGORIES = frozenset({"beach", "nature", "park", "viewpoint"})
OUTDOOR_BIAS_WEIGHT = 0.25  # max pref_match shift at outdoor_bias = +/-1


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _words(*parts) -> set[str]:
    out: set[str] = set()
    for p in parts:
        if isinstance(p, str):
            out.update(p.lower().split())
        elif isinstance(p, (list, tuple)):
            out.update(w for x in p for w in str(x).lower().split())
    return out


def _hour_min(ctx: dict, default: int = 12 * 60) -> int:
    """Activity hour in minutes: explicit `_hour_min` wins, then "HH:MM"."""
    if isinstance(ctx.get("_hour_min"), (int, float)):
        return int(ctx["_hour_min"])
    raw = ctx.get("hour", "12:00")
    return to_min(raw) if ":" in str(raw) else int(raw) * 60


def _state(ctx: dict, hour_min: int) -> dict | None:
    """Dynamic state for this hour, only when trip_ctx built the context."""
    if not ctx.get("dynamic_state"):
        return None
    return trip_ctx.state_at(hour_min, ctx.get("trip"), ctx.get("profile"), ctx)


def score_poi(poi: dict, user: dict | None = None, ctx: dict | None = None) -> dict:
    user, ctx = user or {}, ctx or {}
    reasons: list[str] = []
    parts: dict[str, float] = {}

    rating = float(poi.get("rating") or 0.0)
    parts["rating"] = max(0.0, min(1.0, rating / 5.0))
    if rating >= 4.5:
        reasons.append(f"rating cao {rating}")

    budget = int(user.get("budget", (ctx.get("trip") or {}).get("budget", 3000000)))
    fee = int(poi.get("fee", 0))
    parts["price"] = _clamp(1.0 - fee / budget) if budget > 0 else 0.0
    # Onboarding spending level: align the POI price band with what the party
    # wants to spend (1 budget / 2 mid / 3 high). Unknown price (null) counts as
    # the middle band (`UNKNOWN_PRICE_LEVEL`), so missing data is never a bonus.
    gap = abs(price_level_of(poi) - _int(user.get("spending_level"), 2))
    parts["price"] = 0.5 * parts["price"] + 0.5 * _clamp(1.0 - gap / 2.0)
    if fee == 0:
        reasons.append("mien phi")

    fitness = int(user.get("fitness", 2))
    gap = abs(int(poi.get("intensity", 2)) - fitness)
    parts["effort"] = max(0.0, 1.0 - gap / 2.0)
    if gap == 0:
        reasons.append("vua suc")

    want = _words(user.get("food_prefs", []), user.get("activities", []),
                  (ctx.get("trip") or {}).get("activities", []))
    have = _words(poi.get("tags", []), poi.get("type", ""),
                  poi.get("cuisine", []), poi.get("ambience", ""))
    hit = want & have
    parts["pref_match"] = min(1.0, len(hit) / 2.0) if want else 0.5
    if hit:
        reasons.append("hop gu: " + ", ".join(sorted(hit)))
    # TASTE (own additive component): how much of the ONBOARDING food prefs
    # this POI actually serves, minus an exclusive cuisine clash (vegan-only
    # venue for a BBQ/seafood eater). Only food POIs score; everything else
    # sits at the neutral 0.5 so the component never punishes a beach.
    taste_unit, taste_hits, clashes = profile_filter.taste_score(
        poi, user.get("food_prefs", []))
    parts["taste"] = _clamp(TASTE_NEUTRAL + 0.5 * taste_unit)
    if taste_unit > 0:
        reasons.append("dung gu an: " + ", ".join(taste_hits))
    elif clashes:
        reasons.append("lech gu an (" + ", ".join(clashes) + ")")
    # outdoor_bias (-1..1): push outdoor/weather-sensitive POIs up or down.
    bias = max(-1.0, min(1.0, _num(user.get("outdoor_bias", 0.0))))
    ptype_bias = poi_category(poi) or str(poi.get("type") or "")
    if bias and (ptype_bias in OUTDOOR_CATEGORIES
                 or poi.get("weather_sensitive")):
        parts["pref_match"] = _clamp(parts["pref_match"]
                                     + OUTDOOR_BIAS_WEIGHT * bias)
        reasons.append("hop gu ngoai troi" if bias > 0 else "han che ngoai troi")

    hour_min = _hour_min(ctx)
    hour = hour_min // 60
    # Category-aware: the snapshot keeps the English category in `cat` and a
    # Vietnamese label in `type`; fixtures only carry `type`.
    ptype = poi_category(poi) or poi.get("type", "")
    if ptype in NIGHT_TYPES and hour < NIGHT_START // 60:
        # E2: a bar/nightlife stop in the morning is a semantic mismatch.
        parts["time_fit"] = 0.1
        reasons.append("bar/ nightlife truoc 17h")
    elif hour >= 18 and ptype in ("restaurant", "landmark"):
        parts["time_fit"] = 1.0
        reasons.append("hop buoi toi")
    elif 11 <= hour <= 14 and ptype == "restaurant":
        parts["time_fit"] = 1.0
        reasons.append("gio an")
    elif 11 <= hour <= 15 and poi.get("weather_sensitive") and ptype in ("nature", "beach"):
        parts["time_fit"] = 0.3
        reasons.append("nang gat buoi trua")
    else:
        parts["time_fit"] = 0.7

    # Weather is per HOUR when the trip context carries the forecast (the
    # old ctx only had one rain_prob, so the branch was dead for planning);
    # legacy callers keep the flat rain_prob.
    rain = (trip_ctx.rain_at_hour(ctx, hour_min) if ctx.get("hourly")
            else float(ctx.get("rain_prob", 0.0)))
    if poi.get("weather_sensitive") and rain > 0.5:
        parts["weather"] = 0.2
        reasons.append("mua, han che ngoai troi")
    else:
        parts["weather"] = 1.0

    score = sum(WEIGHTS[k] * parts[k] for k in WEIGHTS)
    state = _state(ctx, hour_min)
    if state is not None:
        mult, state_reasons = trip_ctx.poi_multiplier(poi, state)
        score *= mult
        reasons.extend(state_reasons)
    score = round(_clamp(score), 4)
    return {"score": score, "reasons": reasons or ["mac dinh"]}


def rank(pois: list[dict], user: dict | None = None,
         ctx: dict | None = None) -> list[dict]:
    """POIs sorted desc by score, each {poi_id, score, reasons}.

    With a dynamic-state ctx the score is the mean over the trip's hourly
    grid (see module docstring); reasons come from the worst hour plus the
    start hour so the planner can explain why a POI fits badly.
    """
    ctx = ctx or {}
    hours = ctx.get("hours") if ctx.get("dynamic_state") else None
    scored = []
    for poi in pois:
        if not hours:
            entry = {"poi_id": poi.get("poi_id"), **score_poi(poi, user, ctx)}
        else:
            per = [score_poi(poi, user, {**ctx, "_hour_min": m})
                   for m in hours]
            avg = sum(r["score"] for r in per) / len(per)
            worst = min(per, key=lambda r: r["score"])
            start = per[0]
            reasons: list[str] = []
            for r in (worst, start):
                for reason in r["reasons"]:
                    if reason not in reasons:
                        reasons.append(reason)
            entry = {"poi_id": poi.get("poi_id"), "score": round(avg, 4),
                     "reasons": reasons[:4] or ["mac dinh"]}
        scored.append(entry)
    return sorted(scored, key=lambda r: r["score"], reverse=True)
