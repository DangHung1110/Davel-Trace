"""Objective v1: where the planner's taste lives (doc "Davel - Ham muc tieu v1").

Hard constraints stay in the CP-SAT model: what physics forbids (opening hours,
reachable legs, no overlap, verified POIs, one booked session) and what the
traveller said (must_visit, avoid, budget, return time, named activities, the
lunch of a day that spans it, `strict_rules`). Every other rule of thumb is a
term of one objective, so a plan may break it when that is worth the cost:

    J =  sum_i v_i x_i                          T1 value: one function (value.py)
       + w_state * S - w_rain * W               T2 time-of-day state and rain (trip_ctx bands)
       - sum_g beta_g sum_{k>=2} rho_k y_gk     T3 repeats inside a diversity group
       - gamma sum beta_g a_ij [same group]     T4 two stops of one group back to back
       + sum_s B_s z_s                          T5 a meal in each meal window of the day
       - A * (extra meals in a slot + every pair of restaurants)       T6 (A2: the
                                                solver's "under 2.5 h" test is always
                                                true, so pairs further apart pay too)
       + R(pace) * r                            T7 the siesta right after lunch
       - sum_{k>K0} kappa_k s_k                 T8 stops beyond the comfortable count
       - sum c_ij a_ij                          T9 riding minutes, long legs, zone changes
       + w_edge * sum q_ij a_ij                 T10 PATM transition bonus
       - sum_k sigma_k d_k                      T11 near-duplicates: same site, area +
                                                stop inside it, 2nd market, same dish
       - w_wait * idle minutes                  measured only: w_wait is 0 in v1 and the
                                                solver has no such term (`features`)

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

# The terms of J that `features` reads off a finished day (the learner's columns).
# `rain` (T2's rain cost) and `meal_far` (restaurant pairs 2.5 h or more apart, which
# the solver's A2 also charges) are their own columns so a learner can tell them from
# `state` and `meal_crowd`.
FEATURES = ("value", "state", "rain", "repeat", "adjacent", "meal", "meal_crowd",
            "meal_far", "rest", "pace", "ride", "long_leg", "zone", "edge",
            "same_site", "umbrella", "market", "dish", "wait")


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

    def rain_weight(self) -> float:
        """T2's rain cost weight; 1.0 (the solver before 26/11) when a file has none."""
        return float(self.w.get("w_rain", 1.0))

    def rest_bonus(self, scaled: bool = True) -> float:
        base = float((self.w.get("rest_bonus") or {}).get(str(self.pace), 0.0))
        return base * (self.coef("rest_scale") if scaled else 1.0)

    def beta(self, group: str) -> float:
        return float((self.w.get("beta") or {}).get(group, 1.0)) if group else 0.0


def search_budget(deterministic_time: float, spec: "Spec | None") -> float:
    """The CP-SAT work budget of a solve under this objective (`search_scale`).

    25/11: at the legacy 5 units a thrifty day ended 32% below its optimum (three
    restaurants, two back to back) and 8 units reached 93%, so v1 got 1.6. The search
    was slow for reasons of the model, not of the objective: the A2 restaurant pairs
    and the meal/slot window tests were time disjunctions its LP did not see, and the
    greedy seed did not know v1. With those fixed (26/11, optimizer.py) 1.2 gives a
    better plan than 1.6 did before on average (222 audit solves: +3.0%, 26 better,
    19 worse) and every one-day bench_latency request ends under 8 s; about a third
    of the days never prove optimal, so they always spend the whole budget."""
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


def shown_acts(activities: list[dict]) -> list[dict]:
    """A plan's activities -> the input of `features`: [{poi_id, start (min)}] in
    visiting order, at the times the plan shows (HH:MM strings or minutes)."""
    from BE.common import to_min

    out = []
    for act in activities or []:
        if not act.get("poi_id"):
            continue
        start = act.get("start")
        out.append({"poi_id": act["poi_id"],
                    "start": int(start) if isinstance(start, (int, float)) else to_min(start)})
    return out


def state_terms(acts: list[dict], stubs: dict, bands: list | None,
                scores: dict | None = None, costs: dict | None = None) -> tuple[float, float]:
    """T2 of a finished day, read from its times the way CP-SAT scores it: a stop is
    probed at its visit quartiles (start + d//4 and start + 3d//4, d = the stop's
    visit minutes), and a probe inside band k adds half of (multiplier - 1) to the
    state and half of the band's rain cost to the rain (`optimizer.optimize`,
    DYNAMIC STATE). Returns (state, rain) in U, before w_state and w_rain."""
    state = rain = 0.0
    for act in acts:
        pid = act["poi_id"]
        dur = int(stubs[pid].visit_min)
        for num, den in ((1, 4), (3, 4)):
            probe = int(act["start"]) + dur * num // den
            for k, (lo, hi) in enumerate(bands or []):
                if not lo <= probe < hi:
                    continue
                mult = (scores or {}).get((pid, k))
                if mult is not None:
                    state += (float(mult) - 1.0) / 2
                rain += float((costs or {}).get((pid, k)) or 0.0) / 2
    return state, rain


def is_lunch(stub, start: int) -> bool:
    """The day's lunch as the solver's siesta sees it: a restaurant starting 11:00-13:00,
    or a booked class over the lunch slot."""
    from BE.app.services.soft_rules import LUNCH_REQUIRED, MEAL_SLOTS

    if stub.booking:
        return start < MEAL_SLOTS[0][1] and start + int(stub.visit_min) > MEAL_SLOTS[0][0]
    return bool(stub.restaurant) and LUNCH_REQUIRED[0] <= start < LUNCH_REQUIRED[1]


def idle_minutes(acts: list[dict], stubs: dict, travel: dict,
                 rest_minutes: int | None = None) -> float:
    """Minutes a finished day stands idle between two stops: the gap beyond the ride
    and the `STOP_OVERHEAD_MIN` the solver reserves after each stop. After lunch on a
    day with a siesta the rest is not idle (the gap may run to `rest_minutes`). The
    time before the first stop and after the last is the traveller's, not idle."""
    from BE.app.services.optimizer import STOP_OVERHEAD_MIN

    idle = 0.0
    for a, b in zip(acts, acts[1:]):
        stub = stubs[a["poi_id"]]
        start = int(a["start"])
        allowed = int(travel.get((a["poi_id"], b["poi_id"]), 0)) + STOP_OVERHEAD_MIN
        if rest_minutes and is_lunch(stub, start):
            allowed = max(allowed, int(rest_minutes))
        idle += max(0, int(b["start"]) - (start + int(stub.visit_min)) - allowed)
    return idle


def rest_taken(acts: list[dict], stubs: dict, spec: Spec, rest_minutes: int | None) -> bool:
    """T7 of a finished day, read from its times like the solver's soft siesta: one
    lunch (a restaurant starting 11:00-13:00, or a booked class over the lunch slot)
    and no stop inside the `rest_minutes` after it ends. A siesta the traveller made
    strict is a constraint, not a bonus, so it earns nothing here."""
    if rest_minutes is None or "REST_FOLLOWS_LUNCH" in spec.strict:
        return False
    spans = [(int(a["start"]), int(a["start"]) + int(stubs[a["poi_id"]].visit_min),
              stubs[a["poi_id"]]) for a in acts]
    ends = {end for start, end, stub in spans if is_lunch(stub, start)}
    if len(ends) != 1:
        return False
    rest_start = ends.pop()
    rest_end = rest_start + int(rest_minutes)
    return all(end <= rest_start or start >= rest_end for start, end, _stub in spans)


def features(acts: list[dict], stubs: dict, travel: dict, spec: Spec,
             start_min: int, end_min: int, origin_id: str | None = None,
             edge_scores: dict | None = None, bands: list | None = None,
             state_scores: dict | None = None, state_costs: dict | None = None,
             rest_minutes: int | None = None) -> dict:
    """The terms of J for a finished day, in U (before the top-level weights), read
    off the day itself: its stops in order and the times it shows. Nothing is taken
    from the solve that made it, so the same call describes the solver's raw day and
    the day a traveller (or a judge) sees after `profiles._polished` re-timed it.

    `acts`: ordered [{poi_id, start (min)}] (`shown_acts` reads a plan); `stubs`:
    poi_id -> StubPOI of the solve's pool (score, group, zone, restaurant, booking,
    visit_min); `travel`: (a, b) -> minutes; `bands`, `state_scores`, `state_costs`:
    the solve's time bands with their per-(poi, band) multipliers and rain costs
    (trip_ctx); `rest_minutes`: the siesta of the day's limits (None = no T7).
    `objective_value` turns the result into J in U: on the solver's own times it is
    the value CP-SAT maximised, up to rounding (test_objective_features).
    """
    from BE.app.services.soft_rules import MEAL_SLOTS, RESTAURANT_PAIR_MAX_GAP

    unit = max((s.score for s in stubs.values()), default=1.0)
    if unit <= 0:
        unit = 1.0
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
    food = [p for p in order if stubs[p].restaurant and not stubs[p].booking]
    bonus = spec.w.get("meal_bonus") or {}
    for meal, lo, hi in meal_windows(spec, start_min, end_min):
        if any(lo <= starts[p] < hi for p in food):
            f["meal"] += float(bonus.get(meal, 0.0))
    if "A1" not in spec.strict:
        # A booked class is the meal of every slot it overlaps (optimizer `booking_meal`).
        for lo, hi in MEAL_SLOTS:
            hits = sum(1 for p in food if lo <= starts[p] < hi)
            hits += sum(1 for p in order if stubs[p].booking
                        and starts[p] < hi and starts[p] + stubs[p].visit_min > lo)
            f["meal_crowd"] += max(0, hits - 1)
    # The solver's A2 charges EVERY pair of restaurants: its "starts under 2.5 h
    # apart" test is `earlier OR later`, true for any two times. Pairs under 2.5 h
    # stay in `meal_crowd` (the doc's T6), the others go to `meal_far` at the same
    # weight, so J matches the solver and a learner sees the two kinds apart.
    eaten = [p for p in order if stubs[p].restaurant]
    for k, a in enumerate(eaten):
        for b in eaten[k + 1:]:
            near = abs(starts[a] - starts[b]) < RESTAURANT_PAIR_MAX_GAP
            f["meal_crowd" if near else "meal_far"] += 1.0
    # T7
    if rest_taken(acts, stubs, spec, rest_minutes):
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
    # T2
    f["state"], f["rain"] = state_terms(acts, stubs, bands, state_scores, state_costs)
    # T11
    f.update(duplicate_counts([stubs[p] for p in order]))
    # Idle minutes between stops: measured, not optimised (w_wait 0 in v1), so a pilot
    # can tell whether a judge minds the wait before J charges it.
    f["wait"] = idle_minutes(acts, stubs, travel, rest_minutes)
    return f


def objective_value(f: dict, spec: Spec) -> float:
    """J in U from `features` and the spec's weights."""
    return (f["value"] + spec.coef("w_state") * f["state"] - spec.rain_weight() * f["rain"]
            - f["repeat"] * spec.coef("repeat_scale")
            - spec.coef("gamma") * f["adjacent"] + spec.coef("meal_scale") * f["meal"]
            - spec.meal_crowd() * (f["meal_crowd"] + f["meal_far"])
            + f["rest"] * spec.coef("rest_scale")
            - f["pace"] * spec.coef("pace_scale") - spec.coef("tau") * f["ride"]
            - spec.coef("tau_long") * f["long_leg"] - spec.coef("zeta") * f["zone"]
            + spec.coef("w_edge") * f["edge"]
            - sum(spec.duplicate(kind) * f[kind] for kind in ("same_site", "umbrella",
                                                               "market", "dish"))
            - spec.coef("w_wait") * f.get("wait", 0.0))
