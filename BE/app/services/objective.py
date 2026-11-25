"""Objective v1: where the planner's taste lives (doc "Davel - Ham muc tieu v1").

Hard constraints stay in the CP-SAT model: what physics forbids (opening hours,
reachable legs, no overlap, verified POIs, one booked session) and what the
traveller said (must_visit, avoid, budget, return time, named activities, the
lunch of a day that spans it, `strict_rules`). Every other rule of thumb is a
term of one objective, so a plan may break it when that is worth the cost:

    J =  sum_i v_i x_i                          T1 value: one function (value.py)
       + w_state * S                            T2 time-of-day state (trip_ctx bands)
       - sum_g beta_g sum_{k>=2} rho_k y_gk     T3 repeats inside a diversity group
       - gamma sum beta_g a_ij [same group]     T4 two stops of one group back to back
       + sum_s B_s z_s                          T5 a meal in each meal window of the day
       - A * (extra meals in a slot + meal pairs under 2.5 h)          T6
       + R(pace) * r                            T7 the siesta right after lunch
       - sum_{k>K0} kappa_k s_k                 T8 stops beyond the comfortable count
       - sum c_ij a_ij                          T9 riding minutes, long legs, zone changes
       + w_edge * sum q_ij a_ij                 T10 PATM transition bonus
       - sum_k sigma_k d_k                      T11 near-duplicates: same site, area +
                                                stop inside it, 2nd market, same dish

T3 is submodular: the first stop of a group is free, every further one costs
more than the one before. All weights are in units of U, the top candidate score
of the pool (the `unit` the optimizer already scales by), so one number means
the same trade-off for every profile.

Mode: DAVEL_OBJECTIVE = "v1" (default) | "legacy" (the old hard taste rules) |
a path to a weights JSON with the same keys (learned weights drop in as a file).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

from BE.app.services import rules

WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "objective_weights")
LEGACY = "legacy"
# The default objective: v1 since 25/11/2026 (user decision after step 1).
# DAVEL_OBJECTIVE=legacy brings back the old hard taste rules for A/B runs.
DEFAULT = "v1"

# dwell_kind (BE/ml/data/v2_rules.DWELL, 31 kinds) -> diversity group of T3/T4.
# "" = a meal: T5/T6 own restaurants, they never count as a repeat.
GROUP_OF_KIND = {
    "beach": "beach",
    "nature": "nature", "eco_park": "nature", "park": "nature",
    "viewpoint": "viewpoint",
    "religious": "religious", "religious_major": "religious",
    "museum": "history", "gallery": "history", "historic_site": "history",
    "heritage_site": "history", "old_town": "history", "village": "history",
    "outdoor_urban": "urban",
    "market": "market", "shop": "market", "night_market": "market",
    "boat_short": "experience", "cooking_class": "experience",
    "evening_show": "experience", "paid_site": "experience",
    "theme_park_big": "big_park", "water_park": "big_park",
    "indoor_play": "big_park", "island_day_trip": "big_park",
    "cafe": "cafe", "nightlife": "nightlife", "wellness": "wellness",
    "restaurant": "", "breakfast": "", "lodging": "",
}
# Legacy fixtures (no v2.1 record): their `cat`.
GROUP_OF_LEGACY_CAT = {
    "beach": "beach", "nature": "nature", "park": "nature", "viewpoint": "viewpoint",
    "temple": "religious", "museum": "history", "landmark": "urban",
    "attraction": "experience", "market": "market", "shop": "market", "cafe": "cafe",
    "bar": "nightlife", "nightlife": "nightlife", "spa": "wellness", "restaurant": "",
}

# Rules a traveller can make hard again by naming them in `trip["strict_rules"]`:
# the taste layer of the one book of rules (rules.py).
STRICTABLE = rules.TASTE

FOOD_TOUR_WORDS = ("food tour", "an uong", "am thuc", "an vat", "an het", "tour an")

# Order of the learned coefficients (`features` keys = weight names in the JSON).
FEATURES = ("value", "state", "repeat", "adjacent", "meal", "meal_crowd", "rest",
            "pace", "ride", "long_leg", "zone", "edge",
            "same_site", "umbrella", "market", "dish")


def mode() -> str:
    return (os.environ.get("DAVEL_OBJECTIVE") or DEFAULT).strip()


def active() -> bool:
    return mode().lower() != LEGACY


@lru_cache(maxsize=8)
def _load(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def weights(version: str | None = None) -> dict:
    """The weights of `version` (default: the active mode); a path loads that file."""
    name = version or mode()
    if name.lower() == LEGACY:
        name = "v1"
    path = name if name.endswith(".json") else os.path.join(WEIGHTS_DIR, f"{name}.json")
    return json.loads(_load(path))


def dwell_kind_of(poi: dict | None) -> str:
    """The v2.1 dwell kind of a POI (31 kinds), "" for a legacy record."""
    from BE.common import is_v21

    poi = poi or {}
    if not is_v21(poi):
        return ""
    source = ((poi.get("provenance") or {}).get("dwell") or {}).get("source") or ""
    kind = source.split(":", 1)[1] if source.startswith("dwell_table_v2:") else ""
    if not kind:
        from BE.ml.data.v2_rules import dwell_kind
        kind = dwell_kind(poi.get("category") or "", poi.get("name") or "",
                          (poi.get("hours") or {}).get("archetype") or "")
    return kind


def diversity_group(poi: dict | None) -> str:
    """T3/T4 group of a POI: its dwell kind folded into 12 groups ("" = a meal)."""
    from BE.common import is_v21
    from BE.app.services.soft_rules import poi_category

    poi = poi or {}
    if is_v21(poi):
        return GROUP_OF_KIND.get(dwell_kind_of(poi), "experience")
    return GROUP_OF_LEGACY_CAT.get(poi_category(poi), "")


# --- T11: near-duplicates -----------------------------------------------------
# A plan that rides less packs stops that sit close together, and the closest are
# often one place under two names. Four kinds, all read from the data:
#   same_site   two stops of one `alt_group` (Đèo Hải Vân / Hải Vân Quan)
#   umbrella    a whole-area stop and a stop inside it: `requires_ticket_of` points
#               at the area (Phố cổ Hội An), or at a POI of the area's alt_group
#               (Phố đi bộ phố cổ walks the same old town). Several stops inside the
#               area stay free (three assembly halls on one walk).
#   market      two daytime markets in a day (Chợ Hàn + Chợ Cồn are one
#               experience 1 km apart); a food tour pays `market_food_tour`.
#   dish        two meals of one main dish in a day (mì Quảng twice): the sourced
#               `tags.dishes` label (BE.common.DISHES), else the dish the name states.
# Counted on the day, not on adjacent legs: a stop slipped in between does not
# escape them (T4 only sees neighbours).
SUBSTITUTE_KINDS = {"market": "day_market"}
# Labels of `BE.common.DISHES` that are a diet, not a dish: a vegetarian eats "món
# chay" at every meal, which is no repeat.
NOT_A_DISH = frozenset({"mon_chay"})
DUPLICATE_RULES = {"same_site": "SAME_SITE", "umbrella": "SAME_SITE",
                   "market": "MARKET_REPEAT", "dish": "SAME_DISH"}


def dish_of(poi: dict | None) -> str:
    """A restaurant's main dish id (`BE.common.DISHES`), "" when none or not a meal.

    The sourced label first (`tags.dishes` of the record; the runtime view carries
    their display names in `dishes`), else the dish its name states."""
    from BE.common import DISHES, dish_ids, dishes_from_name
    from BE.app.services.soft_rules import poi_category

    poi = poi or {}
    # the runtime view carries `cat`, a raw v2.1 record `category` / `role`
    if "restaurant" not in (poi_category(poi), poi.get("category")) and poi.get("role") != "meal":
        return ""
    ids = dish_ids(poi)
    if not ids:
        by_vi = {d["vi"]: key for key, d in DISHES.items()}
        ids = [by_vi[v] for v in poi.get("dishes") or [] if v in by_vi]
    if not ids:
        ids = dishes_from_name(poi.get("name") or poi.get("name_vi") or "")
    ids = [d for d in ids if d not in NOT_A_DISH]
    return ids[0] if ids else ""


def stub_keys(poi: dict, parent: dict | None = None) -> dict:
    """StubPOI fields of the objective: T3/T4 group, T9 zone, T11 keys.

    `parent`: the POI `requires_ticket_of` points to, when the caller has it; its
    alt_group then names the whole area, so any record of the area is an umbrella.
    """
    kind = dwell_kind_of(poi)
    inside = str(poi.get("requires_ticket_of") or "")
    if parent and parent.get("alt_group"):
        inside = f"alt:{parent['alt_group']}"
    return {"group": diversity_group(poi), "zone": str(poi.get("zone") or ""),
            "site": f"alt:{poi['alt_group']}" if poi.get("alt_group") else "",
            "inside": inside, "substitute": SUBSTITUTE_KINDS.get(kind, ""),
            "dish": dish_of(poi)}


def parent_of(poi: dict, pois_by_id: dict | None) -> dict | None:
    """The record `requires_ticket_of` points to: a poi_id, or an OSM ref."""
    ref = poi.get("requires_ticket_of")
    if not ref or not pois_by_id:
        return None
    if ref in pois_by_id:
        return pois_by_id[ref]
    plain = ref[4:] if ref.startswith("osm:") else ref
    for p in pois_by_id.values():
        if (p.get("ext_ids") or {}).get("osm") in (ref, plain):
            return p
    return None


def umbrella_pairs(stubs: list) -> list[tuple[int, int]]:
    """(area, inside) index pairs: stub b sits inside the area stub a stands for."""
    pairs = []
    for b, child in enumerate(stubs):
        key = getattr(child, "inside", "")
        if not key:
            continue
        for a, area in enumerate(stubs):
            if a != b and (area.poi_id == key or (area.site and area.site == key)):
                pairs.append((a, b))
    return pairs


def duplicate_counts(stubs: list) -> dict:
    """T11 on a finished day, in counts (before weights): repeats beyond the first
    of each key, and 1 per inside stop whose area is also in the day."""
    def extra(attr):
        seen: dict[str, int] = {}
        for s in stubs:
            key = getattr(s, attr, "")
            if key:
                seen[key] = seen.get(key, 0) + 1
        return float(sum(c - 1 for c in seen.values()))

    inside = {b for _a, b in umbrella_pairs(stubs)}
    return {"same_site": extra("site"), "umbrella": float(len(inside)),
            "market": extra("substitute"), "dish": extra("dish")}


def _fold(text: str) -> str:
    from BE.app.services.profile_filter import fold
    return fold(text or "")


@dataclass(frozen=True)
class Spec:
    """What one solve needs to know about the objective."""
    w: dict
    k0: int | None          # T8: comfortable number of stops (None = no T8)
    pace: int               # 1 slow .. 3 fast
    food_tour: bool         # T6 drops to `meal_crowd_food_tour`
    strict: frozenset       # rules the traveller made hard
    breakfast: bool         # the day starts early enough for a breakfast bonus

    def coef(self, name: str) -> float:
        return float(self.w.get(name, 0.0))

    @property
    def value(self) -> dict:
        """T1's weights for `value.score` (this profile's, `build_spec`)."""
        return self.w.get("value") or {}

    def duplicate(self, kind: str) -> float:
        """T11 weight of one extra stop of `kind` (same_site / umbrella / market / dish)."""
        if kind == "market" and self.food_tour:
            return self.coef("dup_market_food_tour")
        return self.coef(f"dup_{kind}")

    def meal_crowd(self) -> float:
        return self.coef("meal_crowd_food_tour" if self.food_tour else "meal_crowd")

    def rest_bonus(self, scaled: bool = True) -> float:
        base = float((self.w.get("rest_bonus") or {}).get(str(self.pace), 0.0))
        return base * (self.coef("rest_scale") if scaled else 1.0)

    def beta(self, group: str) -> float:
        return float((self.w.get("beta") or {}).get(group, 1.0)) if group else 0.0


def search_budget(deterministic_time: float, spec: "Spec | None") -> float:
    """The CP-SAT work budget of a solve under this objective. v1 has more terms than
    legacy: at the legacy 5 units a thrifty day ended 32% below its optimum (three
    restaurants, two back to back); 8 units reached 93% (`search_scale`, 25/11)."""
    if spec is None:
        return float(deterministic_time)
    return float(deterministic_time) * float(spec.w.get("search_scale", 1.0))


def strict_rules(trip: dict | None) -> frozenset:
    """Rules this trip keeps hard. DAVEL_TASTE_RULES=hard keeps all of them (A/B runs)."""
    if os.environ.get("DAVEL_TASTE_RULES", "soft").strip().lower() == "hard":
        return STRICTABLE
    asked = (trip or {}).get("strict_rules") or []
    return frozenset(str(rule).upper() for rule in asked) & STRICTABLE


def is_food_tour(trip: dict | None) -> bool:
    words = [_fold(a) for a in (trip or {}).get("activities") or []]
    return any(any(key in w for key in FOOD_TOUR_WORDS) for w in words)


def comfortable_stops(trip: dict, limits: dict | None, w: dict, pace: int) -> int:
    """K0: the template's pace ceiling when it has one, else hours x stops per hour."""
    from BE.app.services import templates

    top = (limits or {}).get("max_stops")
    if top:
        return int(top)
    rate = float((w.get("stops_per_hour") or {}).get(str(pace), 0.65))
    return max(1, round(templates._day_hours(trip) * rate))


def value_weights(w: dict | None = None, profile: str | None = None) -> dict:
    """T1 weights (`value.py`) of `profile`: the shared `value` block with the profile's
    `value` keys over it. A weights file with no `value` block (one that carries only the
    J coefficients) keeps v1's, so it never plans with every POI worth zero."""
    w = w if w is not None else weights()
    src = w if "value" in w else weights("v1")
    over = ((src.get("profiles") or {}).get(profile or "") or {}).get("value") or {}
    return {**(src.get("value") or {}), **over}


def build_spec(trip: dict | None, limits: dict | None = None,
               w: dict | None = None, profile: str | None = None) -> Spec:
    """The solve's spec. `profile` (savings / balanced / experience) applies that
    profile's overrides from the weights file: the three plans of a request are
    the same objective under three weight sets, T1's value weights (`w["value"]`,
    `value_weights`) included."""
    from BE.app.services import templates
    from BE.common import to_min

    trip = trip or {}
    w = dict(w or weights())
    value = value_weights(w, profile)
    w.update((w.get("profiles") or {}).get(profile or "", {}))
    w["value"] = value
    pace = templates._profile_pace(trip) or 2
    start = to_min(trip.get("start_time", "07:00"))
    return Spec(w=w, k0=comfortable_stops(trip, limits, w, pace), pace=pace,
                food_tour=is_food_tour(trip), strict=strict_rules(trip),
                breakfast=start < int(w.get("breakfast_if_start_before", 480)))


def meal_windows(spec: Spec, start_min: int, end_min: int) -> list[tuple[str, int, int]]:
    """T5 windows the day can use: (meal, lo, hi) on the restaurant START."""
    from BE.app.services.soft_rules import DINNER_REQUIRED, LUNCH_REQUIRED

    out = []
    lo, hi = spec.w.get("breakfast_window", [390, 540])
    if spec.breakfast:
        out.append(("breakfast", int(lo), int(hi)))
    out.append(("lunch", LUNCH_REQUIRED[0], LUNCH_REQUIRED[1]))
    out.append(("dinner", DINNER_REQUIRED[0], DINNER_REQUIRED[1]))
    return [(name, a, b) for name, a, b in out if a < end_min and b > start_min]


def arc_cost(spec: Spec, minutes: int, zone_a: str, zone_b: str) -> float:
    """T9 on one leg, in U: riding minutes + the part over `long_leg_min` + a zone change."""
    long_min = max(0, int(minutes) - int(spec.w.get("long_leg_min", 45)))
    change = 1.0 if zone_a and zone_b and zone_a != zone_b else 0.0
    return (spec.coef("tau") * minutes + spec.coef("tau_long") * long_min
            + spec.coef("zeta") * change)


def repeat_cost(spec: Spec, group: str, count: int, scaled: bool = True) -> float:
    """T3 for `count` stops of one group, in U (first stop free)."""
    if not group or count < 2:
        return 0.0
    rho = list(spec.w.get("rho") or [0.35, 0.7, 1.0])
    total = sum(rho[min(k, len(rho) - 1)] for k in range(count - 1))
    return spec.beta(group) * total * (spec.coef("repeat_scale") if scaled else 1.0)


def sight_k0(spec: Spec, start_min: int, end_min: int) -> int | None:
    """T8's comfortable number of SIGHTS: K0 less one per meal window the day spans.

    K0 (`comfortable_stops`) counts every stop of a day with its meals. T8 counts the
    sights plus the meals beyond one per window (`paced_stops`): the day's meals never
    pay the pace (before 25/11 a day at K0 dropped its dinner, the 9th stop cost 0.6U,
    savings 1.2U, of a 1.2U dinner bonus), a third restaurant does (left free, a day
    stacked three mì Quảng shops as quick stops).
    """
    if spec.k0 is None:
        return None
    return max(1, int(spec.k0) - main_meals(spec, start_min, end_min))


def main_meals(spec: Spec, start_min: int, end_min: int) -> int:
    """Lunch and dinner windows the day spans: the meals that never pay T8. A
    breakfast stop is short and optional; it counts like a sight (a 07:00 day let a
    third mì Quảng shop in at 14:00 as its "breakfast")."""
    # A window counts when a meal can start in it and still end the day: a day to
    # 18:00 has no real dinner (window 17:30-20:30), and charging one sight for it
    # left the afternoon empty (test_profile_objectives, 25/11).
    room = 90
    return sum(1 for name, lo, hi in meal_windows(spec, start_min, end_min)
               if name != "breakfast" and max(lo, start_min) <= min(hi, end_min - room))


def paced_stops(sights: int, meals: int, spec: Spec, start_min: int, end_min: int) -> int:
    """What T8 counts: every sight, and the meals beyond lunch and dinner."""
    return sights + max(0, meals - main_meals(spec, start_min, end_min))


def pace_cost(spec: Spec, stops: int, scaled: bool = True, k0: int | None = None) -> float:
    """T8 for `stops` sights (meals excluded), in U, beyond `k0` (default spec.k0)."""
    k0 = spec.k0 if k0 is None else k0
    if k0 is None or stops <= k0:
        return 0.0
    kappa = list(spec.w.get("kappa") or [0.3, 0.6, 1.0])
    total = sum(kappa[min(k, len(kappa) - 1)] for k in range(stops - k0))
    return total * (spec.coef("pace_scale") if scaled else 1.0)


def features(acts: list[dict], stubs: dict, travel: dict, spec: Spec,
             start_min: int, end_min: int, origin_id: str | None = None,
             edge_scores: dict | None = None, state: dict | None = None,
             rest_taken: bool | None = None) -> dict:
    """The terms of J for a finished day, in U (before the 11 top-level weights).

    `acts`: ordered [{poi_id, start (min)}]; `stubs`: poi_id -> StubPOI (score, group,
    zone, restaurant, visit_min); `travel`: (a, b) -> minutes. J in U is
    value + w_state*state - repeat - gamma*adjacent + meal_scale*meal
    - A*meal_crowd + rest - pace - tau*ride - tau_long*long_leg - zeta*zone
    + w_edge*edge, which is what `objective_value` returns.
    """
    from BE.app.services.soft_rules import MEAL_SLOTS, RESTAURANT_PAIR_MAX_GAP

    unit = max((s.score for s in stubs.values()), default=1.0) or 1.0
    order = [a["poi_id"] for a in acts]
    starts = {a["poi_id"]: int(a["start"]) for a in acts}
    f = {name: 0.0 for name in FEATURES}
    f["value"] = sum(stubs[p].score for p in order) / unit
    # T3, T4
    counts: dict[str, int] = {}
    for p in order:
        g = stubs[p].group
        if g:
            counts[g] = counts.get(g, 0) + 1
    f["repeat"] = sum(repeat_cost(spec, g, c, scaled=False) for g, c in counts.items())
    f["adjacent"] = sum(spec.beta(stubs[a].group) for a, b in zip(order, order[1:])
                        if stubs[a].group and stubs[a].group == stubs[b].group)
    # T5, T6
    rest_ids = [p for p in order if stubs[p].restaurant and not stubs[p].booking]
    bonus = spec.w.get("meal_bonus") or {}
    for meal, lo, hi in meal_windows(spec, start_min, end_min):
        if any(lo <= starts[p] < hi for p in rest_ids):
            f["meal"] += float(bonus.get(meal, 0.0))
    crowd = 0
    if "A1" not in spec.strict:
        for lo, hi in MEAL_SLOTS:
            hits = sum(1 for p in rest_ids if lo <= starts[p] < hi)
            crowd += max(0, hits - 1)
    for k, a in enumerate(rest_ids):
        for b in rest_ids[k + 1:]:
            if abs(starts[a] - starts[b]) < RESTAURANT_PAIR_MAX_GAP:
                crowd += 1
    f["meal_crowd"] = float(crowd)
    # T7
    if rest_taken:
        f["rest"] = spec.rest_bonus(scaled=False)
    # T8
    meals = sum(1 for p in order if stubs[p].restaurant)
    counted = paced_stops(len(order) - meals, meals, spec, start_min, end_min)
    f["pace"] = pace_cost(spec, counted, scaled=False, k0=sight_k0(spec, start_min, end_min))
    # T9
    legs = list(zip(order, order[1:]))
    if origin_id and order:
        legs = [(origin_id, order[0])] + legs + [(order[-1], origin_id)]
    long_min = int(spec.w.get("long_leg_min", 45))
    for a, b in legs:
        minutes = int(travel.get((a, b), 0))
        f["ride"] += minutes
        f["long_leg"] += max(0, minutes - long_min)
        za = stubs[a].zone if a in stubs else ""
        zb = stubs[b].zone if b in stubs else ""
        f["zone"] += 1.0 if za and zb and za != zb else 0.0
    # T10 (q * 100 in the model, the value at sco * 1000)
    for a, b in zip(order, order[1:]):
        f["edge"] += float((edge_scores or {}).get((a, b), 0.0)) / 10.0 / unit
    f["state"] = float((state or {}).get("value", 0.0))
    # T11
    f.update(duplicate_counts([stubs[p] for p in order]))
    return f


def objective_value(f: dict, spec: Spec) -> float:
    """J in U from `features` and the spec's weights."""
    return (f["value"] + spec.coef("w_state") * f["state"] - f["repeat"] * spec.coef("repeat_scale")
            - spec.coef("gamma") * f["adjacent"] + spec.coef("meal_scale") * f["meal"]
            - spec.meal_crowd() * f["meal_crowd"] + f["rest"] * spec.coef("rest_scale")
            - f["pace"] * spec.coef("pace_scale") - spec.coef("tau") * f["ride"]
            - spec.coef("tau_long") * f["long_leg"] - spec.coef("zeta") * f["zone"]
            + spec.coef("w_edge") * f["edge"]
            - sum(spec.duplicate(kind) * f[kind] for kind in ("same_site", "umbrella",
                                                               "market", "dish")))
