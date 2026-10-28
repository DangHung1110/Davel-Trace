"""Trip context + dynamic traveler STATE (planning time, per request).

The ranker used to see only a frozen snapshot of the request (`hour` =
start_time, no weather). This module answers the question the planner
actually needs: *when* each stop happens, how full / tired / hot the
traveler will be at that hour, and which daily rhythm the trip can even
contain. Everything here is a pure function of (trip, profile, forecast)
except `build()`, which is the one place that touches the network.

Paper anchors (see docs/meal-state-papers.md, surveyed before this change):
- Meal windows: breakfast 07:00-09:00, lunch 11:30-13:30, snack ~10:00 and
  15:00-16:30, dinner 18:00-20:00; nothing heavy after 21:00.
- Midday 11:00-15:00 is the heat window (UTCI bands), indoor preferred.
- Afternoon dip 13:00-15:00 (Monk 2005) -> light/indoor only.
- Evening social bonus after 18:00 (Kahneman 2004).
- No heavy meal inside the 13:00-14:30 dip.

DESIGN CHOICES (deliberate, documented so the numbers can be argued with):
1. SATIETY is a 0..1 decay since the last meal END, half-life
   `SATIETY_HALF_LIFE_MIN = 150` (2.5 h, the same 2.5 h the A2 restaurant
   rule already uses). A meal counts as eaten when its WINDOW ENDS; while a
   window is still open the previous meal is the reference. That is a
   conservative planning-time approximation: the solver picks the actual
   minute, we only know the rhythm.
2. FATIGUE is accumulated walking minutes over `FATIGUE_REF_MIN = 240`
   (4 h of walking saturates it), at `WALK_MIN_PER_HOUR` by pace. Midday
   heat multiplies accumulated walking (perceived effort, +50 % at
   heat_stress = 1) and the 13:00 dip adds a perceived-fatigue step.
3. HEAT is a UTCI-style band on temp_c (`heat_stress` 0..1). Weather is
   fetched once per request through `weather.fetch_forecast` (short
   timeout, cached); if it is unavailable the state uses
   `DEFAULT_TEMP_C = 30.0` and rain 0.0 and says so
   (`weather_source = "none"`), never crashing the plan.
4. Meal slots are CONDITIONAL: a slot exists only when the trip window
   overlaps at least `MIN_MEAL_OVERLAP = 60` minutes of it. A morning
   half-day gets no lunch (and no forced restaurant rhythm); a full day
   gets breakfast/lunch/snack/dinner when the horizon covers them.

Everything is soft scoring: the hard gate stays the safety net and is not
modified here.
"""

from __future__ import annotations

from BE.app.services import weather as weather_svc
from BE.app.services.soft_rules import (
    meal_slots,
    meal_window_present,
    poi_category,
)
from BE.common import to_min

# --- paper windows ---------------------------------------------------------
# MEAL_WINDOWS / MIN_MEAL_OVERLAP / meal_slots / meal_window_present live in
# soft_rules so the gate, the templates and this state layer share ONE
# definition of a meal window.
HEAVY_CUTOFF = 21 * 60         # nothing heavy after 21:00
DIP_WINDOW = (13 * 60, 15 * 60)   # Monk 2005 afternoon dip
EVENING_START = 18 * 60        # Kahneman 2004 social bonus
MIDDAY = (11 * 60, 15 * 60)    # heat window

# --- satiety / fatigue -----------------------------------------------------
SATIETY_HALF_LIFE_MIN = 150.0
SATIETY_AT_START = 0.8         # ate shortly before leaving (planning prior)
FATIGUE_REF_MIN = 240.0
WALK_MIN_PER_HOUR = {1: 8, 2: 15, 3: 22}
HEAT_FATIGUE_BOOST = 0.5       # midday heat adds up to +50 % walking effort
DIP_FATIGUE_STEP = 15.0        # perceived-fatigue minutes added after 13:00

# --- weather ---------------------------------------------------------------
DEFAULT_TEMP_C = 30.0          # Da Nang planning prior when the API is down
WEATHER_TIMEOUT_S = 3
HEAT_BANDS = (                 # (min_temp, stress, label)
    (-100.0, 0.0, "mat"),
    (26.0, 0.35, "am"),
    (30.0, 0.6, "nong"),
    (32.0, 0.85, "rat nong"),
    (35.0, 1.0, "cuc doan"),
)

# --- optimizer time bands (disjoint, minutes since midnight) ---------------
STATE_BANDS = (
    (5 * 60, 10 * 60),
    (10 * 60, 11 * 60 + 30),
    (11 * 60 + 30, 13 * 60 + 30),
    (13 * 60 + 30, 15 * 60),
    (15 * 60, 18 * 60),
    (18 * 60, 21 * 60),
    (21 * 60, 24 * 60),
)

# --- soft multipliers (never a gate) ---------------------------------------
FOOD_FULL_RESTAURANT = 0.2     # satiety > 0.6 -> restaurant almost ruled out
FOOD_FULL_CAFE = 0.7           # ... a cafe/dessert is still a light option
FOOD_HUNGRY = 1.15
FATIGUE_TREK = 0.7
FATIGUE_REST = 1.1
HEAT_OUTDOOR = 0.6
HEAT_INDOOR = 1.1
DIP_HEAVY = 0.5
DIP_LIGHT = 1.15
EVENING_SOCIAL = 1.15
LATE_HEAVY = 0.5

OUTDOOR_CATEGORIES = frozenset({"beach", "nature", "park", "viewpoint"})
REST_CATEGORIES = frozenset({"cafe", "spa", "museum", "landmark"})
DESSERT_WORDS = ("dessert", "che", "banh ngot", "kem", "sweet")
TREK_WORDS = ("trek", "hike", "adventure", "thac", "nui", "leo")


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def hh(minutes: int) -> str:
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


def _trip_start(trip: dict) -> int:
    return to_min((trip or {}).get("start_time") or "07:00")


def _trip_end(trip: dict) -> int:
    return to_min((trip or {}).get("end_time") or "18:00")


def _pace(profile: dict | None) -> int:
    try:
        return min(3, max(1, int((profile or {}).get("pace") or 2)))
    except (TypeError, ValueError):
        return 2


# --------------------------------------------------------------------------
# Meal slots (conditional: single definition lives in soft_rules)
# --------------------------------------------------------------------------
def daypart(minutes: int) -> str:
    if minutes < 6 * 60:
        return "night"
    if minutes < 11 * 60:
        return "morning"
    if minutes < MIDDAY[1]:
        return "midday"
    if minutes < EVENING_START:
        return "afternoon"
    if minutes < HEAVY_CUTOFF:
        return "evening"
    return "late"


# --------------------------------------------------------------------------
# Weather
# --------------------------------------------------------------------------
def _short_transport(url: str) -> dict:
    from BE.app.services import fetch_json
    return fetch_json(url, timeout=WEATHER_TIMEOUT_S)


def _forecast_hour(forecast: dict | None, minutes: int) -> dict | None:
    """Hourly entry for a local hour (matches HH, like weather.rain_at)."""
    hh_int = int(minutes) // 60
    for entry in (forecast or {}).get("hourly", []):
        at = str(entry.get("at") or "")
        if len(at) >= 13 and at[11:13].isdigit() and int(at[11:13]) == hh_int:
            return entry
    return None


def temp_at(ctx: dict | None, minutes: int) -> float:
    entry = _forecast_hour((ctx or {}).get("_forecast"), minutes)
    if entry is None:
        return _float((ctx or {}).get("temp_c"), DEFAULT_TEMP_C)
    return _float(entry.get("temp_c"), DEFAULT_TEMP_C)


def rain_at_hour(ctx: dict | None, minutes: int) -> float:
    entry = _forecast_hour((ctx or {}).get("_forecast"), minutes)
    if entry is None:
        return _float((ctx or {}).get("rain_prob"), 0.0)
    return _float(entry.get("rain_prob"), 0.0)


def solar_factor(minutes: int) -> float:
    """How much a temperature band actually bites at that hour.

    A 31C evening in Da Nang is not the same exposure as 31C at 13:00: the
    heat rule is about solar load, so the UTCI band is scaled by a solar
    factor (full 11:00-15:00, 0.7 around it, 0.4 morning/evening). The raw
    band stays in `heat_stress` for reporting; the scoring reads
    `heat_effective`.
    """
    minutes = int(minutes)
    if MIDDAY[0] <= minutes <= MIDDAY[1]:
        return 1.0
    if (10 * 60 <= minutes < MIDDAY[0]
            or MIDDAY[1] < minutes <= 17 * 60):
        return 0.7
    return 0.4


def heat_stress(temp_c: float) -> tuple[float, str]:
    """(stress 0..1, label) from a UTCI-style temperature band."""
    stress, label = 0.0, "mat"
    for floor, value, name in HEAT_BANDS:
        if temp_c >= floor:
            stress, label = value, name
    return stress, label


def _exposure(poi: dict) -> float:
    """Outdoor exposure 0..1: smart_tags first, then weather_sensitive/type."""
    tags = (poi or {}).get("smart_tags") or {}
    value = tags.get("outdoor_exposure")
    if isinstance(value, (int, float)):
        return _clamp(value)
    if (poi or {}).get("weather_sensitive"):
        return 0.75
    return 1.0 if poi_category(poi) in OUTDOOR_CATEGORIES else 0.1


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
def satiety_at(minutes: int, trip: dict | None, slots: list[dict] | None = None
               ) -> float:
    """0..1 fullness: 1.0 at a HEAVY meal's end, exponential decay after.

    Only real meals (breakfast/lunch/dinner) anchor the decay: a snack is a
    light option, it must not reset fullness (otherwise a 15:00 cafe would
    make the 17:00 traveler look fed and suppress dinner). The paper's snack
    windows are used by the rank time_fit, not by this anchor.
    """
    slots = meal_slots(trip) if slots is None else slots
    ends = [s["end"] for s in slots
            if not s.get("snack") and s["end"] <= int(minutes)]
    if not ends:
        # No heavy meal has ended yet: the traveler left shortly after eating.
        elapsed = max(0, int(minutes) - _trip_start(trip or {}))
        return _clamp(SATIETY_AT_START * 0.5 ** (elapsed / SATIETY_HALF_LIFE_MIN))
    elapsed = max(0, int(minutes) - max(ends))
    return _clamp(0.5 ** (elapsed / SATIETY_HALF_LIFE_MIN))


def fatigue_at(minutes: int, trip: dict | None, profile: dict | None,
               heat: float = 0.0) -> float:
    """0..1 fatigue from walked minutes, midday heat and the 13:00 dip."""
    minutes = int(minutes)
    start = _trip_start(trip or {})
    elapsed_h = max(0.0, (minutes - start) / 60.0)
    walked = elapsed_h * WALK_MIN_PER_HOUR[_pace(profile)]
    if MIDDAY[0] <= minutes <= MIDDAY[1]:
        walked *= 1.0 + HEAT_FATIGUE_BOOST * _clamp(heat)
    if minutes > DIP_WINDOW[0]:
        walked += DIP_FATIGUE_STEP
    return _clamp(walked / FATIGUE_REF_MIN)


def state_at(minutes: int, trip: dict | None = None,
             profile: dict | None = None,
             ctx: dict | None = None) -> dict:
    """Full planning-time state at one minute of the day."""
    minutes = int(minutes)
    trip = trip or {}
    temp_c = temp_at(ctx, minutes)
    stress, band = heat_stress(temp_c)
    slots = (ctx or {}).get("meal_slots") or meal_slots(trip)
    satiety = satiety_at(minutes, trip, slots)
    fatigue = fatigue_at(minutes, trip, profile, stress)
    dip = DIP_WINDOW[0] <= minutes < DIP_WINDOW[1]
    evening = minutes >= EVENING_START
    late = minutes >= HEAVY_CUTOFF
    return {
        "minute": minutes,
        "hour": hh(minutes),
        "daypart": daypart(minutes),
        "satiety": round(satiety, 3),
        "fatigue": round(fatigue, 3),
        "temp_c": round(temp_c, 1),
        "heat_stress": stress,
        "heat_effective": round(stress * solar_factor(minutes), 3),
        "heat_band": band,
        "rain_prob": round(rain_at_hour(ctx, minutes), 3),
        "afternoon_dip": dip,
        "evening_bonus": evening,
        "late_night": late,
        "light_only": bool(dip or fatigue >= 0.8 or (stress >= 0.85 and evening)),
        "meal_window": next(
            (s["name"] for s in slots if s["start"] <= minutes < s["end"]),
            None),
        "meal_slots": [s["name"] for s in slots],
    }


def poi_multiplier(poi: dict, state: dict,
                   profile: dict | None = None) -> tuple[float, list[str]]:
    """Soft state preference for one POI at one hour: (multiplier, reasons).

    Stacks satiety, fatigue, heat, dip and evening rules. It never zeroes a
    POI (0.2 floor per rule keeps everything above 0) and the hard gate still
    decides feasibility; this only re-orders/chooses placements.
    """
    poi = poi or {}
    cat = poi_category(poi)
    exposure = _exposure(poi)
    outdoor = bool(exposure >= 0.55 or cat in OUTDOOR_CATEGORIES
                   or poi.get("weather_sensitive"))
    words = " ".join(str(w) for w in (poi.get("tags") or [])) + " " + str(
        poi.get("ambience") or "") + " " + str(poi.get("name") or "")
    words = words.lower()
    dessert = cat == "cafe" or any(w in words for w in DESSERT_WORDS)
    trek = cat in {"nature", "beach"} and (
        int(poi.get("intensity") or 2) >= 2 or exposure >= 0.7
        or any(w in words for w in TREK_WORDS))
    satiety = _float(state.get("satiety"))
    fatigue = _float(state.get("fatigue"))
    stress = _float(state.get("heat_effective",
                              state.get("heat_stress")))
    # A stop inside the breakfast window IS breakfast (the prior "ate before
    # leaving" must not suppress the one meal the day still needs).
    breakfast = state.get("meal_window") == "breakfast"
    reasons: list[str] = []
    mult = 1.0

    # 1. Satiety: just ate -> no second meal.
    if not breakfast and (cat == "restaurant"
                          or (cat == "market" and "food" in words)):
        if satiety > 0.6:
            mult *= FOOD_FULL_RESTAURANT
            reasons.append("no, vua an xong")
        elif satiety < 0.35:
            mult *= FOOD_HUNGRY
            reasons.append("doi, hop bua an")
    elif not breakfast and dessert and satiety > 0.6:
        mult *= FOOD_FULL_CAFE
        reasons.append("vua an, chi hop do nhe")

    # 2. Fatigue: trek/adventure down, restful stop up.
    if fatigue > 0.6:
        if trek:
            mult *= FATIGUE_TREK
            reasons.append("met, giam di bo/leo")
        elif cat in REST_CATEGORIES and not outdoor:
            mult *= FATIGUE_REST
            reasons.append("met, uu tien cho nghi")
        if state.get("light_only") and (trek or cat in {"bar", "market"}):
            mult *= 0.8

    # 3. Heat: midday sun moves the preference indoors.
    if stress >= 0.6:
        if outdoor and cat not in REST_CATEGORIES:
            mult *= HEAT_OUTDOOR
            reasons.append(f"{state.get('heat_band')}, tranh ngoai troi")
        elif not outdoor:
            mult *= HEAT_INDOOR
            reasons.append("trong nha, do nang")

    # 4. Afternoon dip (13:00-15:00): light/indoor/cafe only.
    if state.get("afternoon_dip"):
        if cat in {"restaurant", "bar", "nature", "beach"} or (
                outdoor and cat != "cafe"):
            mult *= DIP_HEAVY
            reasons.append("dip chieu, chi di nhe")
        elif cat in REST_CATEGORIES:
            mult *= DIP_LIGHT
            reasons.append("dip chieu, hop cho nhe")

    # 5. Evening social/food bonus (after 18:00).
    if state.get("evening_bonus"):
        if cat in {"restaurant", "bar", "market"} and satiety < 0.6:
            mult *= EVENING_SOCIAL
            reasons.append("toi, hop an uong/xa hoi")
        elif cat == "cafe" and satiety < 0.4:
            mult *= 1.1

    # 6. Nothing heavy after 21:00.
    if state.get("late_night") and cat == "restaurant":
        mult *= LATE_HEAVY
        reasons.append("sau 21h, tranh bua nang")

    return round(mult, 3), reasons


# --------------------------------------------------------------------------
# Build (the only network touch)
# --------------------------------------------------------------------------
def build(trip: dict | None, profile: dict | None = None,
          forecast: dict | None = None, fetch_weather: bool = True,
          cache_path: str | None = None) -> dict:
    """Request context: weather + meal slots + hourly state + rank grid.

    Never raises: an unavailable forecast degrades to the planning prior and
    `weather_source = "none"`. `dynamic_state` is True only for an onboarding
    profile so a legacy request keeps its old rank behaviour.
    """
    trip = trip or {}
    profile = profile or {}
    slots = meal_slots(trip)
    source, stale, error = "none", False, ""
    if forecast is None and fetch_weather:
        try:
            forecast = weather_svc.fetch_forecast(
                transport=_short_transport,
                cache_path=cache_path or weather_svc.DEFAULT_CACHE)
            source = str(forecast.get("source") or "open-meteo")
            stale = bool(forecast.get("stale"))
        except Exception as exc:  # noqa: BLE001 - offline must not break a plan
            error = str(exc)[:160]
    elif forecast is not None:
        source = str(forecast.get("source") or "injected")
        stale = bool(forecast.get("stale"))

    start, end = _trip_start(trip), _trip_end(trip)
    hours = list(range(start, end + 1, 60))
    hourly = [{
        "at": hh(m),
        "temp_c": round(temp_at({"_forecast": forecast}, m), 1),
        "rain_prob": round(rain_at_hour({"_forecast": forecast}, m), 3),
    } for m in hours]
    temps = [h["temp_c"] for h in hourly if h["temp_c"] is not None]
    rains = [h["rain_prob"] for h in hourly]
    temp_c = max(temps) if temps and forecast else DEFAULT_TEMP_C
    rain_prob = max(rains) if rains and forecast else 0.0
    stress, band = heat_stress(temp_c)

    ctx = {
        "trip": trip,
        "profile": profile,
        "meal_slots": slots,
        "hours": hours,
        "hourly": hourly,
        "temp_c": round(temp_c, 1),
        "rain_prob": round(rain_prob, 3),
        "heat_stress": stress,
        "heat_band": band,
        "dynamic_state": bool(profile),
        "weather_source": source,
        "weather_stale": stale,
        "weather_error": error,
        "state": state_at(start, trip, profile, {"meal_slots": slots,
                                                "temp_c": temp_c,
                                                "rain_prob": rain_prob,
                                                "_forecast": forecast}),
        "_forecast": forecast,
    }
    return ctx


def optimizer_state(ctx: dict | None, pois: list[dict]
                    ) -> tuple[list[tuple[int, int]], dict[tuple[str, int], float]]:
    """Time bands + per-(poi, band) soft multiplier for the CP-SAT objective.

    Bands are disjoint and clipped to the trip horizon (>= 30 min), so a
    single stop lands in exactly one band. The multiplier is the state rule
    evaluated at the band's midpoint: the same beach that is fine at 08:00
    is penalized when the model places it at 14:00.
    """
    ctx = ctx or {}
    start, end = _trip_start(ctx.get("trip") or {}), _trip_end(ctx.get("trip") or {})
    bands = []
    for lo, hi in STATE_BANDS:
        a, b = max(lo, start), min(hi, end)
        if b - a >= 30:
            bands.append((a, b))
    scores: dict[tuple[str, int], float] = {}
    for k, (lo, hi) in enumerate(bands):
        state = state_at((lo + hi) // 2, ctx.get("trip"), ctx.get("profile"), ctx)
        for poi in pois:
            mult, _reasons = poi_multiplier(poi, state, ctx.get("profile"))
            scores[(poi.get("poi_id"), k)] = mult
    return bands, scores


def edge_state(ctx: dict | None) -> dict:
    """State used by the transition scorer (no per-arc clock exists).

    Anchor: 14:30 (or 30 min before the trip ends), i.e. the post-lunch
    "still full" moment that decides whether another meal makes sense.
    """
    ctx = ctx or {}
    trip = ctx.get("trip") or {}
    anchor = min(_trip_end(trip) - 30, 14 * 60 + 30)
    anchor = max(_trip_start(trip), anchor)
    return state_at(anchor, trip, ctx.get("profile"), ctx)


def compact_state(ctx: dict | None, minutes: int) -> dict:
    """Small per-activity state attached to a plan response."""
    state = state_at(minutes, (ctx or {}).get("trip"),
                     (ctx or {}).get("profile"), ctx)
    return {key: state[key] for key in (
        "hour", "daypart", "satiety", "fatigue", "temp_c", "heat_stress",
        "heat_effective", "heat_band", "rain_prob", "afternoon_dip",
        "evening_bonus", "light_only")}


def plan_report(ctx: dict | None) -> dict:
    """Serializable state evidence attached to a plan (no callables)."""
    ctx = ctx or {}
    trip = ctx.get("trip") or {}
    bands = optimizer_state(ctx, [])[0]
    return {
        "meal_slots": [{"name": s["name"], "start": hh(s["start"]),
                        "end": hh(s["end"]), "heavy": s["heavy"]}
                       for s in ctx.get("meal_slots") or []],
        "temp_c": ctx.get("temp_c"),
        "rain_prob": ctx.get("rain_prob"),
        "heat_band": ctx.get("heat_band"),
        "weather_source": ctx.get("weather_source"),
        "weather_stale": bool(ctx.get("weather_stale")),
        "bands": [{"start": hh(lo), "end": hh(hi),
                   "state": state_at((lo + hi) // 2, trip,
                                     ctx.get("profile"), ctx)}
                  for lo, hi in bands],
        "edge_state": edge_state(ctx),
        "dynamic_state": bool(ctx.get("dynamic_state")),
    }
