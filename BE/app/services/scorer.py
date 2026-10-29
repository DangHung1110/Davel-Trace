"""Transition scorer: q_ij for the optimizer (T030, lane B). Model or rule.

score_transition(a, b, user, ctx) -> float (positive: a->b preferred).
Backend: LightGBM BE/ml/patm/model.txt when present. Features come from
the lane-A T026+T062+T063b extractor (21 features) when that module is
importable; the in-file STUB mirror (`_STUB_FEATURE_NAMES`, 16 features)
is the fallback in a clean checkout. A width guard compares the loaded
booster's feature count
against the ACTIVE extractor: on mismatch the scorer falls back to the
nac-1 RULE instead of crashing (stated in describe()). Rule weights +
stub feature code mirror lane-A rule_score.py/features.py. Rule path
averages microseconds (target <5ms).

Inputs are plain POI dicts (type/intensity/rating/tags/...).
"""

from __future__ import annotations

import os

from BE.app.services.soft_rules import edge_penalty

MODEL_PATH = os.path.join("BE", "ml", "patm", "model.txt")

_STUB_FEATURE_NAMES = (
    "d_intensity", "d_rating", "d_price", "d_duration",
    "x_meal_after", "x_indoor_buffer", "x_intensity_drop", "x_same_type",
    "u_pace", "u_fitness", "u_spending", "u_outdoor",
    "c_hour", "c_rain", "c_daylight_left", "c_weekend",
)

_bst = None
_backend = "rule"
_note = ""
_lane_cache = None


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _lane_a_extract():
    """(extract_fn, width) once: lane-A T026+T062 extractor, else stub 16f.

    Resolved lazily and cached in a module global — feature extraction runs
    ~n^2 times, the import attempt must not repeat per call.
    """
    global _lane_cache
    if _lane_cache is None:
        try:
            from BE.ml.patm.features import FEATURE_NAMES as lane_names
            from BE.ml.patm.features import extract
            _lane_cache = (extract, len(lane_names))
        except Exception:  # noqa: BLE001 - clean checkout has no BE/ml/patm
            _lane_cache = (None, len(_STUB_FEATURE_NAMES))
    return _lane_cache


def _norm_poi(p: dict) -> dict:
    """Tolerate the flat `visit_min: int` shape used by the profile/replan
    callers; the lane-A extractor expects `{"p50": ...}`. Dicts pass through."""
    vm = p.get("visit_min")
    if isinstance(vm, (int, float)):
        return {**p, "visit_min": {"p50": vm}}
    return p


def _features(a: dict, b: dict, user: dict | None, ctx: dict | None) -> list[float]:
    """Active extractor: lane-A when importable, else the 16f stub mirror."""
    extract, _n = _lane_a_extract()
    if extract is not None:
        return extract(_norm_poi(a), _norm_poi(b), user, ctx)
    return _stub_features(_norm_poi(a), _norm_poi(b), user, ctx)


def _stub_features(a: dict, b: dict, user: dict | None, ctx: dict | None) -> list[float]:
    """STUB mirror of lane-A T026 extract (16). Used when lane-A is absent."""
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
    global _bst, _backend, _note
    if _bst is not None:
        return True
    if not os.path.exists(path):
        _backend = "rule"
        _note = f"model file not found: {path}"
        return False
    try:
        import lightgbm as lgb
        _bst = lgb.Booster(model_file=path)
    except Exception as exc:  # noqa: BLE001 - never crash: fall back to rule
        _bst = None
        _backend = "rule"
        _note = f"model load failed: {exc}"
        return False
    width = _lane_a_extract()[1]
    if _bst.num_feature() != width:
        _note = (f"model expects {_bst.num_feature()} features, "
                 f"extractor gives {width}")
        _bst = None
        _backend = "rule"
        return False
    _backend = "model"
    _note = ""
    return True


def describe() -> dict:
    _ensure_model()
    return {"backend": _backend, "model_path": MODEL_PATH,
            "n_features": _lane_a_extract()[1], "note": _note}


def score_transition(a: dict, b: dict, user: dict | None = None,
                     ctx: dict | None = None, model_path: str = MODEL_PATH) -> float:
    if _ensure_model(model_path):
        import numpy as np
        x = np.array(_features(a, b, user, ctx), dtype=float).reshape(1, -1)
        return float(_bst.predict(x)[0] - 0.5)  # center ~[-0.5, 0.5]
    return _rule(a, b)


def edge_scores(ids: list[str], by_id: dict, user: dict | None = None,
                ctx: dict | None = None) -> dict[tuple[str, str], float]:
    """q_ij for every ordered pair (optimizer T017 input).

    TASK-2 soft layer: A2 (back-to-back restaurants) and B1 (same-type
    neighbours, cafe->cafe / viewpoint->sunset_view exempt) subtract a small
    pair penalty from the learned/rule transition score.
    state layer: when `ctx` carries the trip context, `edge_penalty` also
    applies the satiety-aware food transition (trip_ctx.edge_state), so a
    still-full traveler is nudged away from another meal.
    """
    return {(a, b): round(score_transition(by_id[a], by_id[b], user, ctx)
                          + edge_penalty(by_id[a], by_id[b], ctx), 4)
            for a in ids for b in ids if a != b}
