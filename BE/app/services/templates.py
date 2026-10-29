"""Day templates V1 (3 hard archetypes) + profile -> template selection.

A template is an ORDERED slot list `{type, start_hint}` plus a rest window
tied to lunch. It constrains the optimizer through concrete inputs: required
category presence, pace stop count (min/max), an intensity ceiling, and the
rest window (no activity may overlap it).

UNIVERSAL human needs (every template, every archetype, and a custom profile
without an archetype): lunch 11:00-13:00 with exactly one restaurant, and a
solver-locked rest window that STARTS at that restaurant's END time (60 min
at pace 1, 45 at pace 2, 30 at pace 3) and shrinks to fit a late lunch, never
below 20 min. There is no fixed 13:00 anchor any more; the model pins the
window to the chosen lunch activity. At most one dinner restaurant is still
enforced by gate A1. Adding an explicit `rest_after_lunch` input to the
optimizer is the same mechanism the family template used to have
(`blocked_window`), now tied to the lunch variable instead of a clock.

- A `family-slow`: 5-6 stops, a locked rest block right after lunch (no
  trek/adventure (nature excluded, intensity <= 2, no nightlife)).
- B `friends-fast`: 7-8 stops, nightlife allowed, late end (>= 20:00 when the
  trip horizon allows it).
- C `couple-calm`: 6 stops, culture + food focus, slow pace, intensity <= 2.

Selection is a pure function of the profile (party_type first, then
pace/fitness/activities, accessibility downgrades pace). It is deliberately
explicit and unit-tested; no LLM call decides the template.

Slot types use the canonical English categories from `soft_rules.poi_category`
(restaurant, cafe, market, attraction, landmark, museum, beach, nature, park,
viewpoint, bar, spa). The optimizer only needs category sets + counts, so a
slot list without enough real POIs is relaxed by `attempts()` (stop count and
required counts relax; the archetype bans and the rest lock stay hard).
"""

from __future__ import annotations

import re

from BE.app.services.profile_filter import fold
from BE.app.services.soft_rules import (
    FOOD_CATEGORIES,
    LUNCH_REQUIRED,
    REST_DEFAULT_MIN,
    REST_MIN_BY_PACE,
    SIGHTSEEING_CATEGORIES,
    meal_window_present,
)
from BE.common import to_min

MARKET = frozenset({"market"})
CULTURE = frozenset({"museum", "landmark", "attraction"})
# Every snapshot activity category (lodging/transport are not activities).
ALL_ACTIVITY = frozenset({
    "restaurant", "cafe", "market", "attraction", "landmark", "museum",
    "beach", "nature", "park", "viewpoint", "bar", "nightlife", "spa",
})

DAY_TEMPLATES: dict[str, dict] = {
    "family-slow": {
        "label": "Gia dinh nhe nhang",
        "slots": [
            {"type": "attraction", "start_hint": "08:30"},
            {"type": "cafe", "start_hint": "10:00"},
            {"type": "restaurant", "start_hint": "11:00"},
            {"type": "park", "start_hint": "13:15"},
            {"type": "market", "start_hint": "14:45"},
            {"type": "cafe", "start_hint": "16:15"},
        ],
        "rest_block": {"minutes": 60,
                       "label": "nghi trua (sau khi an trua, theo nhip)"},
        "pace_stops": (5, 6),
        "allowed_categories": (FOOD_CATEGORIES | SIGHTSEEING_CATEGORIES | MARKET)
                              - frozenset({"nature"}),
        "required_groups": (("restaurant", FOOD_CATEGORIES),
                            ("cafe", frozenset({"cafe"})),
                            ("sightseeing", SIGHTSEEING_CATEGORIES)),
        "max_intensity": 2,
        "late_end_min": None,
    },
    "friends-fast": {
        "label": "Ban be nhanh",
        "slots": [
            {"type": "landmark", "start_hint": "08:00"},
            {"type": "cafe", "start_hint": "09:15"},
            {"type": "attraction", "start_hint": "10:30"},
            {"type": "restaurant", "start_hint": "11:30"},
            {"type": "market", "start_hint": "14:00"},
            {"type": "cafe", "start_hint": "15:30"},
            {"type": "restaurant", "start_hint": "17:30"},
            {"type": "bar", "start_hint": "20:00"},
        ],
        "rest_block": {"minutes": 30,
                       "label": "nghi trua (sau khi an trua, theo nhip)"},
        "pace_stops": (7, 8),
        "allowed_categories": ALL_ACTIVITY,
        "required_groups": (("restaurant", frozenset({"restaurant"})),
                            ("cafe", frozenset({"cafe"}))),
        "max_intensity": 3,
        "late_end_min": 20 * 60,  # 20:00, only enforced when the horizon allows
    },
    "couple-calm": {
        "label": "Cap doi thu tha",
        "slots": [
            {"type": "cafe", "start_hint": "09:00"},
            {"type": "museum", "start_hint": "10:15"},
            {"type": "restaurant", "start_hint": "11:45"},
            {"type": "landmark", "start_hint": "13:30"},
            {"type": "cafe", "start_hint": "15:30"},
            {"type": "market", "start_hint": "16:45"},
        ],
        "rest_block": {"minutes": 45,
                       "label": "nghi trua (sau khi an trua, theo nhip)"},
        "pace_stops": (6, 6),
        "allowed_categories": (FOOD_CATEGORIES | CULTURE | MARKET
                               | frozenset({"beach", "park", "viewpoint"})),
        "required_groups": (("restaurant", frozenset({"restaurant"})),
                            ("cafe", frozenset({"cafe"})),
                            ("culture", CULTURE)),
        "max_intensity": 2,
        "late_end_min": None,
    },
}

DEFAULT_TEMPLATE = "couple-calm"

# Legacy path: a request that never sent an onboarding profile keeps the old
# behaviour (no archetype bans, no pace band, no rest lock). The router passes
# template="" for those; None still means "derive from trip.profile".
NO_LIMITS = {
    "template": None,
    "min_stops": None,
    "max_stops": None,
    "required_any": [],
    "blocked_window": None,
    "rest_after_lunch": False,
    "late_end_min": None,
    "max_intensity": None,
    "allowed_categories": None,
    "lunch_required": False,
    "rest_minutes": None,
}

# Folded party-type hints (see profile_filter.fold: "gia đình" -> "gia dinh").
FAMILY_HINTS = ("family", "gia dinh", "kid", "child", "children", "tre em",
                "con nho", "elder", "elderly", "senior", "bo me")
FRIENDS_HINTS = ("friend", "ban be", "group", "nhom", "team", "dong nghiep",
                 "company", "hoi ban")
COUPLE_HINTS = ("couple", "cap doi", "honeymoon", "trang mat", "partner",
                "nguoi yeu", "doi")

FAST_ACTIVITY_HINTS = ("nightlife", "bar", "pub", "club", "party", "parties",
                       "tiec")
CALM_ACCESSIBILITY = frozenset({"wheelchair", "stroller", "low_walking",
                                "no_stairs", "low walking", "no stairs"})


def _int(value, default: int = 2) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _has(text: str, hints: tuple[str, ...]) -> bool:
    """Whole-word hint in folded text: "_"/"-" split words and a plural
    s/es is fine ("family_with_kids", "friends"), but "bar" never fires on
    "barbecue" nor "pub" on "public"."""
    words = re.sub(r"[_\-/]+", " ", text or "")
    return any(re.search(r"(?<!\w)" + re.escape(hint) + r"(?:s|es)?(?!\w)", words)
               for hint in hints)


def select_template(profile: dict | None) -> str:
    """Map an onboarding profile to one of the three hard templates.

    Precedence:
    1. party_type: family/kids -> family-slow, friends/group -> friends-fast,
       couple/honeymoon -> couple-calm.
    2. accessibility answers cap the effective pace at 2 (a stroller/wheelchair
       day is a slow day by construction).
    3. fitness/pace 3 or a nightlife/party activity -> friends-fast.
    4. fitness/pace 1 -> family-slow.
    5. neutral -> couple-calm (culture + food, slow).
    """
    profile = profile or {}
    party = fold(str(profile.get("party_type") or ""))
    if _has(party, FAMILY_HINTS):
        return "family-slow"
    if _has(party, FRIENDS_HINTS):
        return "friends-fast"
    if _has(party, COUPLE_HINTS):
        return "couple-calm"

    pace = _int(profile.get("pace"), 2)
    fitness = _int(profile.get("fitness"), 2)
    accessibility = [fold(str(a)) for a in profile.get("accessibility") or []]
    if any(a in CALM_ACCESSIBILITY for a in accessibility):
        pace = min(pace, 2)
    activities = fold(" ".join(str(a) for a in profile.get("activities") or []))

    if fitness >= 3 or pace >= 3 or _has(activities, FAST_ACTIVITY_HINTS):
        return "friends-fast"
    if fitness <= 1 or pace <= 1:
        return "family-slow"
    return DEFAULT_TEMPLATE


def _profile_pace(trip: dict | None) -> int | None:
    """Pace answer of the onboarding profile (1..3), or None when absent."""
    profile = (trip or {}).get("profile") or {}
    if profile.get("pace") is None:
        return None
    return min(3, max(1, _int(profile.get("pace"), 2)))


def _rest_length(name: str, trip: dict | None = None) -> int:
    """Rest length in minutes, driven by the profile pace.

    The static `rest_block.minutes` is the default (no profile); an onboarding
    pace overrides it (pace 1 -> 60, 2 -> 45, 3 -> 30). The WINDOW itself is
    not fixed: the optimizer starts it at the lunch activity's end.
    """
    block = DAY_TEMPLATES[name].get("rest_block") or {}
    pace = _profile_pace(trip or {})
    if pace:
        return REST_MIN_BY_PACE[pace]
    return int(block.get("minutes") or REST_DEFAULT_MIN)


def _lunch_fits_horizon(trip: dict | None) -> bool:
    """Can the lunch rhythm be used inside the trip horizon?

    Paper window 11:30-13:30; a window is present when the trip covers at
    least 60 minutes of it (soft_rules.meal_window_present), so a morning
    half-day is not force-fed a lunch while a 07:00-13:00 day still is.
    """
    return meal_window_present(trip or {}, "lunch")


def lunch_required(trip: dict | None = None) -> bool:
    """Universal lunch: 11:00-13:00 must be usable inside the trip horizon."""
    trip = trip or {}
    if not (trip.get("profile") or {}):
        return False
    return _lunch_fits_horizon(trip)


def template_constraints(name: str, trip: dict | None = None) -> dict:
    """Template -> concrete optimizer inputs, trimmed to the trip horizon.

    The rest length (pace) is dropped when the horizon cannot contain lunch.
    The archetype bans (allowed categories, intensity ceiling) always stay
    hard, and the universal lunch requirement is independent of the archetype.
    """
    template = DAY_TEMPLATES[name]
    trip = trip or {}
    end = to_min(trip.get("end_time", "18:00"))

    late_end = template.get("late_end_min")
    if late_end is not None and end < late_end:
        late_end = None

    needs_lunch = _lunch_fits_horizon(trip)
    rest_minutes = _rest_length(name, trip) if needs_lunch else None
    required_any = [{"count": 1, "categories": sorted(cats)}
                    for _label, cats in template["required_groups"]]
    return {
        "template": name,
        "min_stops": template["pace_stops"][0],
        "max_stops": template["pace_stops"][1],
        "required_any": required_any,
        "blocked_window": None,  # no fixed clock anchor: rest follows lunch
        "rest_after_lunch": needs_lunch,
        "late_end_min": late_end,
        "max_intensity": template.get("max_intensity"),
        "allowed_categories": frozenset(template["allowed_categories"]),
        "lunch_required": needs_lunch,
        "rest_minutes": rest_minutes,
    }


def universal_constraints(trip: dict | None = None) -> dict:
    """Human needs for a custom profile that does not pick an archetype.

    No bans, no pace band, no late end: only the lunch + rest window every
    plan gets (rest starts at lunch end, length by pace). A profile-less
    request stays fully legacy (NO_LIMITS).
    """
    trip = trip or {}
    limits = dict(NO_LIMITS)
    if not (trip.get("profile") or {}):
        return limits
    needs_lunch = lunch_required(trip)
    limits["lunch_required"] = needs_lunch
    limits["rest_after_lunch"] = needs_lunch
    pace = _profile_pace(trip) or 2
    limits["rest_minutes"] = REST_MIN_BY_PACE[pace] if needs_lunch else None
    return limits


def allows(poi: dict | None, template_name: str) -> bool:
    """Router-side check (must_visit pruning): fits the archetype hard bans."""
    poi = poi or {}
    template = DAY_TEMPLATES[template_name]
    category = str(poi.get("cat") or poi.get("type") or "").strip().lower()
    if category and category not in template["allowed_categories"]:
        return False
    ceiling = template.get("max_intensity")
    if ceiling is not None and _int(poi.get("intensity"), 2) > ceiling:
        return False
    return True


def attempts(constraints: dict) -> list[dict]:
    """Fallback ladder: full -> drop stop-count/required -> drop max too.

    The archetype bans, the intensity ceiling, the locked rest window, the
    universal lunch requirement and the hard cafe/adjacency caps are never
    relaxed (they are what makes a plan a plan). A small POI pool may not fill
    7 slots, which is reported through `relaxed_step`.
    """
    full = dict(constraints)
    no_min = {**full, "min_stops": None, "required_any": []}
    no_max = {**no_min, "max_stops": None}
    return [full, no_min, no_max]
