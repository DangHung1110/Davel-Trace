"""Rule scorer nac-1 (T027, lane A). Deterministic order preference.

score_transition(a, b, user, ctx) > 0 means a -> b beats b -> a.
Every term is antisymmetric by construction, so score(b, a) == -score(a, b)
exactly (flip-consistency gate in test_patm.py depends on this).

Base margins (identical to the legacy T028 inline rules, so seed pair
labels are unchanged — backward compat):
  intensity-desc (van dong truoc, thu gian sau, spec US3) ... +/-0.5
  meal-after-activity (an sau hoat dong) ................... +/-0.3
  indoor-buffer (uu tien trong-nha truoc khi thoi tiet doi)  +/-0.2
predict(): |margin| <= TIE_MARGIN (0.15) -> tie (0).

User/ctx modulation applies ONLY on non-default input (default user/ctx
reproduces base margins exactly):
  fitness scales the intensity term: x(0.5 + 0.25*fitness), fitness=2 -> x1
  rain_prob amplifies indoor-buffer: x(1 + rain), rain=0 -> x1
"""

from __future__ import annotations

TIE_MARGIN = 0.15

W_INTENSITY = 0.5
W_MEAL = 0.3
W_INDOOR = 0.2


def _is_food(p: dict) -> bool:
    return p.get("type") == "restaurant"


def _sens(p: dict) -> bool:
    return bool(p.get("weather_sensitive"))


def score_transition(a: dict, b: dict, user: dict | None = None,
                     ctx: dict | None = None) -> float:
    ia, ib = a.get("intensity", 2), b.get("intensity", 2)
    fitness = (user or {}).get("fitness", 2) if user else 2
    rain = (ctx or {}).get("rain_prob", 0.0) if ctx else 0.0

    margin = 0.0
    if ia > ib:
        margin += W_INTENSITY * (0.5 + 0.25 * fitness)
    elif ib > ia:
        margin -= W_INTENSITY * (0.5 + 0.25 * fitness)
    if not _is_food(a) and _is_food(b):
        margin += W_MEAL
    elif not _is_food(b) and _is_food(a):
        margin -= W_MEAL
    if _sens(a) and not _sens(b):
        margin -= W_INDOOR * (1.0 + rain)
    elif _sens(b) and not _sens(a):
        margin += W_INDOOR * (1.0 + rain)
    return round(margin, 3)


def explain_transition(a: dict, b: dict, user: dict | None = None,
                       ctx: dict | None = None) -> list[str]:
    fired: list[str] = []
    ia, ib = a.get("intensity", 2), b.get("intensity", 2)
    if ia != ib:
        fired.append("intensity-desc")
    if _is_food(a) != _is_food(b):
        fired.append("meal-after-activity")
    if _sens(a) != _sens(b):
        fired.append("indoor-buffer")
    _ = (user, ctx)
    return fired


def predict(a: dict, b: dict, user: dict | None = None,
            ctx: dict | None = None) -> int:
    m = score_transition(a, b, user, ctx)
    return 1 if m > TIE_MARGIN else (-1 if m < -TIE_MARGIN else 0)
