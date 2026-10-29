"""Transition feature extractor, 21 features (T026 + T062 M1 + T063b, lane A).

Four groups x4 (research R2) + M mobility prior + X continuous exposure.
Ordered pair (a, b); every feature is derived from attributes/user/context —
NEVER from absolute POI identifiers (the unit test enforces their absence
below).

Groups:
  A attr deltas  F(a)-F(b) ......... d_intensity, d_rating, d_price, d_duration
  B cross ordered (antisymmetric [*]) x_meal_after, x_indoor_buffer,
      x_intensity_drop, x_same_type (symmetric, swap-invariant)
  C user (centered; neutral user = 0) u_pace, u_fitness, u_spending, u_outdoor
  D context .................... c_hour, c_rain, c_daylight_left, c_weekend
  M mobility (T062, directional) prior_logp = log P(cat(b)|cat(a), bucket)
  X exposure (T063b) ........... x_outdoor_exposure, x_rain_cover,
      x_sun_exposure, x_wind_exposure  (all antisymmetric diffs)

[*] swap-negating features make flip-consistent models easy; the
symmetric x_same_type is the documented exception.

Exposure features read ``smart_tags.outdoor_exposure`` /
``sun_exposure`` / ``wind_exposure`` / ``rain_cover`` (written by
``BE.ml.data.enrich_snapshot``) and fall back to the coarse canonical-type
preset when a POI is not enriched yet.  ``rain_cover`` is mapped to
enclosed 0.0 / mixed 0.5 / covered 0.7 / open 1.0 / unknown 0.5.

[*] Hook fulfilled: `train.py` interim 10-feature extractor replaced by
`extract` (same ordered-pair input, 21 outputs).
"""

from __future__ import annotations

FEATURE_NAMES = (
    "d_intensity", "d_rating", "d_price", "d_duration",
    "x_meal_after", "x_indoor_buffer", "x_intensity_drop", "x_same_type",
    "u_pace", "u_fitness", "u_spending", "u_outdoor",
    "c_hour", "c_rain", "c_daylight_left", "c_weekend",
    "prior_logp",
    "x_outdoor_exposure", "x_rain_cover", "x_sun_exposure", "x_wind_exposure",
)

N_FEATURES = len(FEATURE_NAMES)
assert N_FEATURES == 21

FOOD_TYPES = ("restaurant",)
OUTDOOR_TYPES = ("nature", "beach", "landmark")
RAIN_COVER_VALUES = {"enclosed": 0.0, "mixed": 0.5, "covered": 0.7,
                     "open": 1.0, "unknown": 0.5}

DEFAULT_USER = {"pace": 2, "fitness": 2, "spending_level": 2, "outdoor_bias": 0.0}
DEFAULT_CTX = {"hour": 9, "rain_prob": 0.0, "daylight_left_h": 8.0, "is_weekend": False}


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _canon(raw: str) -> str:
    try:
        from BE.ml.patm.estimate_duration import canonical_category
        return canonical_category(raw or "")
    except Exception:  # noqa: BLE001 - prior JSON absent in other worktrees
        return raw or ""


def _is_food(p: dict) -> float:
    return 1.0 if _canon(p.get("type", "")) in FOOD_TYPES else 0.0


def _sens(p: dict) -> float:
    return 1.0 if p.get("weather_sensitive") else 0.0


def _smart_tags(p: dict) -> dict:
    st = p.get("smart_tags")
    return st if isinstance(st, dict) else {}


def _clamp01(value) -> float:
    return max(0.0, min(1.0, _num(value, 0.5)))


def _type_default(p: dict, key: str):
    """Coarse canonical-type exposure preset; None when unavailable."""
    try:
        from BE.ml.weather_label.labeler import type_exposure
        return type_exposure(_canon(p.get("type", ""))).get(key)
    except Exception:  # noqa: BLE001 - other worktrees may lack the labeler
        return None


def _outdoor(p: dict) -> float:
    """Continuous outdoor exposure: smart_tags first, type rule fallback."""
    st = _smart_tags(p)
    if st.get("outdoor_exposure") is not None:
        return _clamp01(st.get("outdoor_exposure"))
    return 1.0 if _canon(p.get("type", "")) in OUTDOOR_TYPES else 0.0


def _exposure(p: dict, key: str) -> float:
    st = _smart_tags(p)
    if st.get(key) is not None:
        return _clamp01(st.get(key))
    if key == "outdoor_exposure":
        return _outdoor(p)
    default = _type_default(p, key)
    return 0.5 if default is None else _clamp01(default)


def _rain_cover(p: dict) -> float:
    st = _smart_tags(p)
    value = str(st.get("rain_cover", "")).strip().lower()
    if value in RAIN_COVER_VALUES:
        return RAIN_COVER_VALUES[value]
    default = _type_default(p, "rain_cover")
    return RAIN_COVER_VALUES.get(str(default or "unknown"), 0.5)


def _same_type(a: dict, b: dict) -> float:
    return 1.0 if _canon(a.get("type", "")) == _canon(b.get("type", "")) else 0.0


def extract(a: dict, b: dict, user: dict | None = None,
            ctx: dict | None = None) -> list[float]:
    """21 features for ordered transition a -> b."""
    u = {**DEFAULT_USER, **(user or {})}
    c = {**DEFAULT_CTX, **(ctx or {})}
    ia, ib = _num(a.get("intensity"), 2), _num(b.get("intensity"), 2)
    fa, fb = _is_food(a), _is_food(b)
    sa, sb = _sens(a), _sens(b)
    try:
        from BE.ml.patm.estimate_duration import canonical_category
        from BE.ml.patm.prior import logprob
        hour = int(_num(c.get("hour"), 9))
        m_prior = logprob(canonical_category(b.get("type", "")),
                          canonical_category(a.get("type", "")), hour)
    except Exception:  # noqa: BLE001 - prior JSON absent in other worktrees
        m_prior = 0.0
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
        _same_type(a, b),
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
        # M: mobility prior (directional log-prob)
        m_prior,
        # X: continuous exposure diffs (T063b, antisymmetric)
        _outdoor(a) - _outdoor(b),
        _rain_cover(a) - _rain_cover(b),
        _exposure(a, "sun_exposure") - _exposure(b, "sun_exposure"),
        _exposure(a, "wind_exposure") - _exposure(b, "wind_exposure"),
    ]
