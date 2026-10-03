"""Transition scorer: q_ij for the optimizer (T030, lane B). Model or rule.

score_transition(a, b, user, ctx) -> float (positive: a->b preferred).
Backend: LightGBM BE/ml/patm/model.txt when present (16 features, same
names as lane-A T026); otherwise nac-1 RULE fallback (stated in
describe()). STUB-NOTE: rule weights + feature code mirror lane-A
rule_score.py/features.py (absent in this worktree); phase-PR replaces
them with imports. Rule path averages microseconds (target <5ms).

Inputs are plain POI dicts (type/intensity/rating/tags/...).
"""

from __future__ import annotations

import os

MODEL_PATH = os.path.join("BE", "ml", "patm", "model.txt")

FEATURE_NAMES = (
    "d_intensity", "d_rating", "d_price", "d_duration",
    "x_meal_after", "x_indoor_buffer", "x_intensity_drop", "x_same_type",
    "u_pace", "u_fitness", "u_spending", "u_outdoor",
    "c_hour", "c_rain", "c_daylight_left", "c_weekend",
)

_bst = None
_backend = "rule"


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _features(a: dict, b: dict, user: dict | None, ctx: dict | None) -> list[float]:
    """STUB mirror of lane-A T026 extract (16). Replaced at phase-PR."""
    u = {"pace": 2, "fitness": 2, "spending_level": 2, "outdoor_bias": 0.0, **(user or {})}
    c = {"hour": 9, "rain_prob": 0.0, "daylight_left_h": 8.0, "is_weekend": False,
         **(ctx or {})}
    ia, ib = _num(a.get("intensity"), 2), _num(b.get("intensity"), 2)
    fa = 1.0 if a.get("type") == "restaurant" else 0.0
    fb = 1.0 if b.get("type") == "restaurant" else 0.0
    sa = 1.0 if a.get("weather_sensitive") else 0.0
    sb = 1.0 if b.get("weather_sensitive") else 0.0
    return [
        ia - ib, _num(a.get("rating")) - _num(b.get("rating")),
        _num(a.get("price_level"), 2) - _num(b.get("price_level"), 2),
        _num((a.get("visit_min") or {}).get("p50"), 60)
        - _num((b.get("visit_min") or {}).get("p50"), 60),
        fb - fa, (sa * (1.0 - sb)) - (sb * (1.0 - sa)),
        1.0 if ia > ib else (-1.0 if ib > ia else 0.0),
        1.0 if a.get("type") == b.get("type") else 0.0,
        _num(u.get("pace"), 2) - 2.0, _num(u.get("fitness"), 2) - 2.0,
        _num(u.get("spending_level"), 2) - 2.0, _num(u.get("outdoor_bias"), 0.0),
        _num(c.get("hour"), 9) / 12.0 - 1.0, _num(c.get("rain_prob"), 0.0),
        _num(c.get("daylight_left_h"), 8.0) / 12.0,
        1.0 if c.get("is_weekend") else 0.0,
    ]


def _rule(a: dict, b: dict) -> float:
    """STUB mirror of lane-A T027 (default user/ctx). Replaced at phase-PR."""
    # ponytail: no model.txt -> nac-1 rule fallback is the deliberate
    # offline ceiling; describe() reports which backend answered.
    m = 0.0
    ia, ib = a.get("intensity", 2), b.get("intensity", 2)
    if ia > ib:
        m += 0.5
    elif ib > ia:
        m -= 0.5
    if a.get("type") != "restaurant" and b.get("type") == "restaurant":
        m += 0.3
    elif b.get("type") != "restaurant" and a.get("type") == "restaurant":
        m -= 0.3
    if a.get("weather_sensitive") and not b.get("weather_sensitive"):
        m -= 0.2
    elif b.get("weather_sensitive") and not a.get("weather_sensitive"):
        m += 0.2
    return round(m, 3)


def _ensure_model(path: str = MODEL_PATH) -> bool:
    global _bst, _backend
    if _bst is not None:
        return True
    if not os.path.exists(path):
        _backend = "rule"
        return False
    import lightgbm as lgb
    _bst = lgb.Booster(model_file=path)
    _backend = "model"
    return True


def describe() -> dict:
    _ensure_model()
    return {"backend": _backend, "model_path": MODEL_PATH,
            "n_features": len(FEATURE_NAMES)}


def score_transition(a: dict, b: dict, user: dict | None = None,
                     ctx: dict | None = None, model_path: str = MODEL_PATH) -> float:
    if _ensure_model(model_path):
        import numpy as np
        x = np.array(_features(a, b, user, ctx), dtype=float).reshape(1, -1)
        return float(_bst.predict(x)[0] - 0.5)  # center ~[-0.5, 0.5]
    return _rule(a, b)


def edge_scores(ids: list[str], by_id: dict, user: dict | None = None,
                ctx: dict | None = None) -> dict[tuple[str, str], float]:
    """q_ij for every ordered pair (optimizer T017 input)."""
    return {(a, b): score_transition(by_id[a], by_id[b], user, ctx)
            for a in ids for b in ids if a != b}
