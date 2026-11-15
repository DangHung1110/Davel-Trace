"""Transition scorer: q_ij for the optimizer (T030, lane B). Model or rule.

score_transition(a, b, user, ctx) -> float (positive: a->b preferred).
Backend: LightGBM BE/ml/patm/model.txt over the 21 features of
`BE.ml.patm.features`. A model file that is missing, cannot load (lightgbm needs
libomp on macOS) or has another feature count falls back to the nac-1 RULE
instead of crashing (stated in describe()). Rule path averages microseconds
(target <5ms).

Inputs are plain POI dicts (type/intensity/rating/tags/...).
"""

from __future__ import annotations

import os

from BE.app.services.soft_rules import edge_penalty, poi_category
from BE.ml.patm.features import FEATURE_NAMES, extract

MODEL_PATH = os.path.join("BE", "ml", "patm", "model.txt")


_bst = None
_backend = "rule"
_note = ""


def _norm_poi(p: dict) -> dict:
    """Tolerate the flat `visit_min: int` shape used by the profile/replan
    callers; the extractor expects `{"p50": ...}`. Dicts pass through."""
    vm = p.get("visit_min")
    if isinstance(vm, (int, float)):
        return {**p, "visit_min": {"p50": vm}}
    return p


def _features(a: dict, b: dict, user: dict | None, ctx: dict | None) -> list[float]:
    return extract(_norm_poi(a), _norm_poi(b), user, ctx)


def _rule(a: dict, b: dict) -> float:
    """Nac-1 rule at the default user/ctx: what plans run on when the model cannot load."""
    m = 0.0
    ia, ib = a.get("intensity", 2), b.get("intensity", 2)
    if ia > ib:
        m += 0.5
    elif ib > ia:
        m -= 0.5
    food_a, food_b = poi_category(a) == "restaurant", poi_category(b) == "restaurant"
    if food_b and not food_a:
        m += 0.3
    elif food_a and not food_b:
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
    # Validate into a local, publish last: profiles plan in parallel threads,
    # so a half-checked booster must never be visible through `_bst`.
    try:
        import lightgbm as lgb
        booster = lgb.Booster(model_file=path)
    except Exception as exc:  # noqa: BLE001 - never crash: fall back to rule
        _backend = "rule"
        _note = f"model load failed: {exc}"
        return False
    width = len(FEATURE_NAMES)
    if booster.num_feature() != width:
        _note = (f"model expects {booster.num_feature()} features, "
                 f"extractor gives {width}")
        _backend = "rule"
        return False
    _bst = booster
    _backend = "model"
    _note = ""
    return True


def describe() -> dict:
    _ensure_model()
    return {"backend": _backend, "model_path": MODEL_PATH,
            "n_features": len(FEATURE_NAMES), "note": _note}


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

    The model scores all n*(n-1) pairs in ONE batched predict (same values as
    `score_transition` per pair): per-pair predict calls cost ~4 s per profile
    at 116 candidates and serialise the parallel profile solves on the GIL.
    """
    pairs = [(a, b) for a in ids for b in ids if a != b]
    if pairs and _ensure_model():
        import numpy as np
        x = np.array([_features(by_id[a], by_id[b], user, ctx)
                      for a, b in pairs], dtype=float)
        learned = [float(v - 0.5) for v in _bst.predict(x)]
    else:
        learned = [_rule(by_id[a], by_id[b]) for a, b in pairs]
    return {(a, b): round(score + edge_penalty(by_id[a], by_id[b], ctx), 4)
            for (a, b), score in zip(pairs, learned)}
