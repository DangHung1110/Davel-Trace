"""Transition feature extractor, 16 features (T026, lane A).

Four groups x4 (research R2). Ordered pair (a, b); every feature is
derived from attributes/user/context — NEVER from absolute POI
identifiers (the unit test enforces their absence below).

Groups:
  A attr deltas  F(a)-F(b) ......... d_intensity, d_rating, d_price, d_duration
  B cross ordered (antisymmetric [*]) x_meal_after, x_indoor_buffer,
      x_intensity_drop, x_same_type (symmetric, swap-invariant)
  C user (centered; neutral user = 0) u_pace, u_fitness, u_spending, u_outdoor
  D context .................... c_hour, c_rain, c_daylight_left, c_weekend

[*] swap-negating features make flip-consistent models easy; the
symmetric x_same_type is the documented exception.

[*] Hook fulfilled: `train.py` interim 10-feature extractor replaced by
`extract` (same ordered-pair input, 16 outputs).
"""

from __future__ import annotations

FEATURE_NAMES = (
    "d_intensity", "d_rating", "d_price", "d_duration",
    "x_meal_after", "x_indoor_buffer", "x_intensity_drop", "x_same_type",
    "u_pace", "u_fitness", "u_spending", "u_outdoor",
    "c_hour", "c_rain", "c_daylight_left", "c_weekend",
)

N_FEATURES = len(FEATURE_NAMES)
assert N_FEATURES == 16

FOOD_TYPES = ("restaurant",)
OUTDOOR_TYPES = ("nature", "beach", "landmark")

DEFAULT_USER = {"pace": 2, "fitness": 2, "spending_level": 2, "outdoor_bias": 0.0}
DEFAULT_CTX = {"hour": 9, "rain_prob": 0.0, "daylight_left_h": 8.0, "is_weekend": False}


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _is_food(p: dict) -> float:
    return 1.0 if p.get("type") in FOOD_TYPES else 0.0


def _sens(p: dict) -> float:
    return 1.0 if p.get("weather_sensitive") else 0.0


def _outdoor(p: dict) -> float:
    return 1.0 if p.get("type") in OUTDOOR_TYPES else 0.0


def extract(a: dict, b: dict, user: dict | None = None,
            ctx: dict | None = None) -> list[float]:
    """16 features for ordered transition a -> b."""
    u = {**DEFAULT_USER, **(user or {})}
    c = {**DEFAULT_CTX, **(ctx or {})}
    ia, ib = _num(a.get("intensity"), 2), _num(b.get("intensity"), 2)
    fa, fb = _is_food(a), _is_food(b)
    sa, sb = _sens(a), _sens(b)
    return [
        # A: attr deltas
        ia - ib,
        _num(a.get("rating")) - _num(b.get("rating")),
        _num(a.get("price_level"), 2) - _num(b.get("price_level"), 2),
        _num((a.get("visit_min") or {}).get("p50"), 60)
        - _num((b.get("visit_min") or {}).get("p50"), 60),
        # B: cross ordered
        fb - fa,
        (sa * (1.0 - sb)) - (sb * (1.0 - sa)),
        1.0 if ia > ib else (-1.0 if ib > ia else 0.0),
        1.0 if a.get("type") == b.get("type") else 0.0,
        # C: user centered
        _num(u.get("pace"), 2) - 2.0,
        _num(u.get("fitness"), 2) - 2.0,
        _num(u.get("spending_level"), 2) - 2.0,
        _num(u.get("outdoor_bias"), 0.0),
        # D: context
        _num(c.get("hour"), 9) / 12.0 - 1.0,
        _num(c.get("rain_prob"), 0.0),
        _num(c.get("daylight_left_h"), 8.0) / 12.0,
        1.0 if c.get("is_weekend") else 0.0,
    ]
