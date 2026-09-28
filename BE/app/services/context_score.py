"""Context scorer (T023, lane C). Preference -> attribute mapping.

score_context(poi, prefs, ctx) -> {"score": 0..1, "fired": [{rule, reason}]}.
Rules (spec, each explainable):
- quiet: "yên tĩnh"/"tĩnh lặng" -> ambience yên tĩnh/tĩnh + crowd vắng/vừa.
- dating: "hẹn hò"/"lãng mạn"/"romantic" -> ambience lãng mạn/yên tĩnh + rating>=4.5.
- recovery: "sau hiking"/"sau leo núi"/"mệt" -> recovery types
  (beach/massage/cafe/restaurant) + intensity<=2.
- near_sea: "gần biển" -> type beach / tags biển (proxy; ctx may carry
  sea_dist_km for exact scoring later).

No-keyword-match -> neutral 0.5, fired empty. Stdlib only.
"""

from __future__ import annotations

RECOVERY_TYPES = ("beach", "massage", "cafe", "restaurant")
QUIET_AMBIENCE = ("yên tĩnh", "tĩnh lặng", "tĩnh")
QUIET_CROWD = ("vắng", "vừa phải", "ít người")
DATING_AMBIENCE = ("lãng mạn", "romantic", "yên tĩnh")


def _has(text: str, *keywords: str) -> bool:
    low = text.lower()
    return any(k in low for k in keywords)


def _join_prefs(prefs) -> str:
    if isinstance(prefs, str):
        return prefs
    return " ".join(str(p) for p in (prefs or []))


def score_context(poi: dict, prefs=None, ctx: dict | None = None) -> dict:
    ctx = ctx or {}
    want = _join_prefs(prefs)
    fired: list[dict] = []
    scores: list[float] = []

    if _has(want, "yên tĩnh", "tĩnh lặng"):
        amb, crowd = str(poi.get("ambience", "")).lower(), str(poi.get("crowd", "")).lower()
        s = (0.6 if _has(amb, *QUIET_AMBIENCE) else 0.2) + \
            (0.4 if _has(crowd, *QUIET_CROWD) or not crowd else 0.0)
        fired.append({"rule": "quiet", "reason": f"ambience {poi.get('ambience')} + crowd {poi.get('crowd')}"})
        scores.append(min(1.0, s))

    if _has(want, "hẹn hò", "lãng mạn", "romantic"):
        amb = str(poi.get("ambience", "")).lower()
        rating = float(poi.get("rating") or 0.0)
        s = (0.6 if _has(amb, *DATING_AMBIENCE) else 0.2) + \
            (0.4 if rating >= 4.5 else rating / 5.0 * 0.4)
        fired.append({"rule": "dating", "reason": f"ambience {poi.get('ambience')} + rating {rating}"})
        scores.append(min(1.0, s))

    if _has(want, "sau hiking", "sau leo núi", "mệt", "thư giãn", "recovery"):
        rec = poi.get("type") in RECOVERY_TYPES
        calm = int(poi.get("intensity", 2)) <= 2
        s = (0.6 if rec else 0.2) + (0.4 if calm else 0.0)
        fired.append({"rule": "recovery",
                      "reason": f"type {poi.get('type')} + intensity {poi.get('intensity')}"})
        scores.append(min(1.0, s))

    if _has(want, "gần biển"):
        tags = " ".join(str(t) for t in poi.get("tags", [])).lower()
        if poi.get("type") == "beach" or "biển" in tags:
            s = 1.0
        else:
            dist = ctx.get("sea_dist_km")
            s = max(0.0, 1.0 - float(dist) / 10.0) if dist is not None else 0.3
        fired.append({"rule": "near_sea", "reason": f"type {poi.get('type')} + tags"})
        scores.append(s)

    if not fired:
        return {"score": 0.5, "fired": []}
    return {"score": round(sum(scores) / len(scores), 4), "fired": fired}
