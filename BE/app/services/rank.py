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
"""

from __future__ import annotations

from BE.app.services import to_min

WEIGHTS = {
    "rating": 0.25,
    "price": 0.15,
    "effort": 0.15,
    "pref_match": 0.25,
    "time_fit": 0.10,
    "weather": 0.10,
}


def _words(*parts) -> set[str]:
    out: set[str] = set()
    for p in parts:
        if isinstance(p, str):
            out.update(p.lower().split())
        elif isinstance(p, (list, tuple)):
            out.update(w for x in p for w in str(x).lower().split())
    return out


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
    parts["price"] = max(0.0, 1.0 - fee / budget) if budget > 0 else 0.0
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

    hour = to_min(ctx.get("hour", "12:00")) // 60 if ":" in str(ctx.get("hour", "")) \
        else int(ctx.get("hour", 12))
    ptype = poi.get("type", "")
    if hour >= 18 and ptype in ("restaurant", "landmark"):
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

    rain = float(ctx.get("rain_prob", 0.0))
    if poi.get("weather_sensitive") and rain > 0.5:
        parts["weather"] = 0.2
        reasons.append("mua, han che ngoai troi")
    else:
        parts["weather"] = 1.0

    score = round(sum(WEIGHTS[k] * parts[k] for k in WEIGHTS), 4)
    return {"score": score, "reasons": reasons or ["mac dinh"]}


def rank(pois: list[dict], user: dict | None = None,
         ctx: dict | None = None) -> list[dict]:
    """POIs sorted desc by score, each {poi_id, score, reasons}."""
    scored = [{"poi_id": p.get("poi_id"), **score_poi(p, user, ctx)} for p in pois]
    return sorted(scored, key=lambda r: r["score"], reverse=True)
