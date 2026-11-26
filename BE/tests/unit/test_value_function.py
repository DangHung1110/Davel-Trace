"""T1 of objective v1 is ONE function of the POI (value.py) under three weight sets.

Pinned here:
- with the pre-v1 constants as weights (objective_weights/v1.json `value`), balanced and
  experience values are bit-identical to `profiles._score` + taste + lean, so the step
  changes the structure, not those two plans' scores;
- savings is the same formula without its mean matrix leg (riding is T9's alone), and
  its taste / lean unit is the pool's top value, not the most expensive place's |score|;
- the mean leg still ranks the savings candidate cap (`cap_avg_leg`), and only there;
- nothing in value.py reads a profile name: the profiles differ only by weights;
- the explanations and /v1/repair read the same values the solver planned with;
- DAVEL_OBJECTIVE=legacy keeps the old node scores and the ranker's explanations.

Run: python -m pytest BE/tests/unit/test_value_function.py -q
"""

import ast
import inspect
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import objective, profile_filter, profiles, repair, retrieval  # noqa: E402
from BE.app.services import value as value_svc  # noqa: E402

PROFILES = ("savings", "balanced", "experience")


def _poi(pid, cat, rating, fee=0, price_level=1, reviews=None, tags=None, **extra):
    poi = {"poi_id": pid, "name": pid, "cat": cat, "type": cat, "rating": rating,
           "fee": fee, "price_level": price_level, "tags": tags or [cat], "intensity": 1,
           "opening_hours": ["06:00-23:59"], "visit_min": 45, "verified": True}
    if reviews is not None:
        poi["review_count"] = reviews
    poi.update(extra)
    return poi


POOL = [
    _poi("seafood", "restaurant", 4.6, 50_000, 1, 1_200, ["hải sản"], cuisine=["seafood"],
         name="Quán Hải Sản Bé Mặn"),
    _poi("bistro", "restaurant", 4.8, 250_000, 2, 900),
    _poi("dear", "restaurant", 4.3, 850_000, 3, 60),
    _poi("cafe", "cafe", 4.5, 40_000, 1, 300),
    _poi("beach", "beach", 4.4, reviews=5_000, weather_sensitive=True),
    _poi("museum", "museum", 4.7, 60_000, 1, 2_500, ["Bảo tàng"], type="Bảo tàng"),
    _poi("market", "market", 4.2, reviews=12_000),
    _poi("temple", "temple", 4.9, reviews=30_500, tags=["Chùa Phật giáo"], type="Chùa"),
    _poi("park", "park", 3.9),
]
PROFILE = {"party_type": "couple", "pace": 2, "fitness": 2, "spending_level": 1,
           "outdoor_bias": 0.5, "activities": ["beach", "museum"], "food_prefs": ["hải sản"]}
TRIP = {"trip_id": "t", "budget": 3_000_000, "start_time": "08:00", "end_time": "18:00",
        "must_visit": [], "avoid": [], "activities": [], "profile": PROFILE}


def legacy_values(profile, pois, trip, unit=None):
    """The pre-v1 node score of build_plan: `_score` + TASTE_WEIGHT*U0*taste + U0*lean,
    with no mean leg; U0 = max |score| unless `unit` says otherwise."""
    nov = profiles.novelty_scores(pois)
    base = {p["poi_id"]: profiles._score(profile, p, novelty=nov, avg_leg=0.0,
                                         budget=trip.get("budget")) for p in pois}
    if unit is None:
        unit = max((abs(v) for v in base.values()), default=1.0) or 1.0
    prefs = value_svc.taste_prefs(trip)
    person = trip.get("profile") or {}
    liked = retrieval.liked_wishes(person.get("activities"))
    ref = profiles.price_reference(pois)
    out = {}
    for p in pois:
        taste = profile_filter.taste_score(p, prefs)[0]
        lean = profiles.soft_lean(p, person, liked, ref)[0]
        out[p["poi_id"]] = (base[p["poi_id"]] + profiles.TASTE_WEIGHT * unit * taste
                            + unit * lean)
    return out


def scored(profile, pois=POOL, trip=TRIP):
    return value_svc.score(pois, trip, objective.value_weights(profile=profile))


class TestOneFunction(unittest.TestCase):
    def test_balanced_and_experience_are_the_pre_v1_scores_exactly(self):
        for profile in ("balanced", "experience"):
            for trip in (TRIP, {**TRIP, "budget": 800_000},
                         {**TRIP, "profile": {}, "activities": ["ăn hải sản"]}):
                self.assertEqual(scored(profile, trip=trip).values,
                                 legacy_values(profile, POOL, trip), (profile, trip))

    def test_savings_is_the_old_formula_without_the_mean_leg(self):
        for trip in (TRIP, {**TRIP, "budget": 800_000}):
            got = scored("savings", trip=trip)
            nov = profiles.novelty_scores(POOL)
            top = max(profiles._score("savings", p, novelty=nov, avg_leg=0.0,
                                      budget=trip["budget"]) for p in POOL)
            self.assertEqual(got.unit, top)
            self.assertEqual(got.values, legacy_values("savings", POOL, trip, unit=top))

    def test_a_taste_hit_is_a_fifth_of_the_top_value_in_every_profile(self):
        plain = {**TRIP, "profile": {**PROFILE, "food_prefs": [], "spending_level": 2,
                                     "outdoor_bias": 0.0, "activities": []}}
        hungry = {**plain, "profile": {**plain["profile"], "food_prefs": ["hải sản"]}}
        for profile in PROFILES:
            before, after = scored(profile, trip=plain), scored(profile, trip=hungry)
            gain = after.values["seafood"] - before.values["seafood"]
            self.assertAlmostEqual(gain, 0.2 * after.unit, places=9, msg=profile)
        # savings: the 850k kitchen is the pool's largest |score| (-7.8); the old unit made
        # one taste hit worth 0.2 * 7.8 = 1.56, more than the best place (1.4).
        places = scored("savings", trip=plain)
        self.assertLess(places.unit, 2.0)
        self.assertLess(places.values["dear"], -7.0)

    def test_a_profile_is_only_a_weight_set(self):
        source = inspect.getsource(value_svc)
        tree = ast.parse(source)
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef))
                      and node.body and isinstance(node.body[0], ast.Expr)}
        words = {node.value for node in ast.walk(tree)
                 if isinstance(node, ast.Constant) and isinstance(node.value, str)
                 and id(node) not in docstrings}
        self.assertFalse(words & set(PROFILES), "value.py must not branch on a profile")
        shared = objective.weights()["value"]
        for profile in PROFILES:
            own = objective.weights()["profiles"][profile].get("value") or {}
            self.assertEqual(objective.value_weights(profile=profile), {**shared, **own})
            self.assertEqual(objective.build_spec({}, profile=profile).value,
                             {**shared, **own})

    def test_a_weights_file_without_value_keeps_v1s(self):
        learned = {k: v for k, v in objective.weights("v1").items()
                   if k not in ("value", "profiles")}
        for profile in PROFILES:
            self.assertEqual(objective.value_weights(learned, profile),
                             objective.value_weights(objective.weights("v1"), profile))

    def test_the_evidence_follows_the_weights(self):
        savings, balanced, experience = (scored(p).reasons for p in PROFILES)
        self.assertIn("rating cao 4.9", balanced["temple"])
        # cost speaks only where it is weighed (savings), novelty only in experience
        self.assertNotIn("mien phi", balanced["temple"])
        self.assertNotIn("mien phi", experience["temple"])
        self.assertIn("mien phi", savings["temple"])
        self.assertIn("re (40k/nguoi)", savings["cafe"])
        self.assertFalse(any("doc dao, it nguoi biet" in why
                             for why in (*balanced.values(), *savings.values())))
        self.assertIn("dung gu an: hải sản", balanced["seafood"])
        self.assertIn("hop gu ngoai troi", experience["beach"])
        self.assertIn("hop hoat dong ban thich", experience["museum"])
        self.assertIn("hop muc chi tieu", savings["seafood"])
        novel = [pid for pid, why in experience.items() if "doc dao, it nguoi biet" in why]
        nov = value_svc.novelty_scores(POOL)
        self.assertTrue(novel)
        self.assertTrue(all(nov[pid] >= value_svc.NOVEL_REASON for pid in novel))


# Six free beaches alike in all but where they are: three close together, three far out.
BEACHES = [_poi(pid, "beach", 4.4, opening_hours=["00:00-23:59"], visit_min=60)
           for pid in ("a1", "a2", "a3", "z1", "z2", "z3")]
NEAR = {"z1", "z2", "z3"}
CELLS = {f"{a['poi_id']}->{b['poi_id']}": {
    "minutes": 5 if a["poi_id"] in NEAR and b["poi_id"] in NEAR else 40, "km": 1.0}
    for a in BEACHES for b in BEACHES if a is not b}
PLAIN_TRIP = {"trip_id": "t", "budget": 3_000_000, "start_time": "08:00",
              "end_time": "18:00", "must_visit": [], "avoid": []}


class TestTheCapAndThePlan(unittest.TestCase):
    def plan(self, profile, env=None):
        by_id = {p["poi_id"]: p for p in BEACHES}
        with mock.patch.dict(os.environ, {"DAVEL_SOLVER_CANDIDATES": "3", **(env or {})}):
            return profiles.build_plan(profile, PLAIN_TRIP, [{"poi_id": pid} for pid in by_id],
                                       by_id, CELLS, template="")

    def test_the_mean_leg_ranks_only_the_savings_cap(self):
        savings, balanced = self.plan("savings"), self.plan("balanced")
        # savings keeps the compact cluster, balanced (no cap_avg_leg) the ties by id
        self.assertEqual({p["poi_id"] for p in savings["_context"]["pois"]}, NEAR)
        self.assertEqual({p["poi_id"] for p in balanced["_context"]["pois"]}, {"a1", "a2", "a3"})
        # ...and the values the solver planned with carry no leg: alike beaches, alike values
        values = savings["_context"]["values"]
        self.assertEqual(len(set(values.values())), 1, values)
        self.assertEqual(values, {pid: scored("savings", BEACHES, PLAIN_TRIP).values[pid]
                                  for pid in values})

    def test_the_candidates_keep_the_order_they_came_in(self):
        # Only the solver's node order: sorting by value changed days by search path alone
        # and slowed requests (measured 26/11), so the value only decides the cap.
        by_id = {p["poi_id"]: p for p in BEACHES}
        order = ["z3", "a1", "z1", "a3", "z2", "a2"]
        plan = profiles.build_plan("balanced", PLAIN_TRIP, [{"poi_id": pid} for pid in order],
                                   by_id, CELLS, template="")
        self.assertEqual([p["poi_id"] for p in plan["_context"]["pois"]], order)

    def test_legacy_keeps_the_old_scores_and_the_ranker_evidence(self):
        plan = self.plan("balanced", {"DAVEL_OBJECTIVE": "legacy"})
        self.assertNotIn("values", plan["_context"])
        self.assertTrue(plan["activities"])
        self.assertTrue(all(a["explanation"]["source"] == "rank" for a in plan["activities"]))


# One cheap and one dear kitchen, a free beach, a market and a 4.9 temple.
DAY = [_poi("eatery", "restaurant", 4.4, 50_000, 1, opening_hours=["10:00-22:00"]),
       _poi("bistro", "restaurant", 4.8, 250_000, 2, opening_hours=["10:00-22:00"]),
       _poi("beach", "beach", 4.5, opening_hours=["00:00-23:59"], visit_min=60),
       _poi("market", "market", 4.3, opening_hours=["06:00-18:00"]),
       _poi("temple", "temple", 4.9, opening_hours=["06:00-18:00"])]
DAY_CELLS = {f"{a['poi_id']}->{b['poi_id']}": {"minutes": 10, "km": 1.0}
             for a in DAY for b in DAY if a is not b}
DAY_TRIP = {"trip_id": "t", "budget": 3_000_000, "start_time": "08:00", "end_time": "17:00",
            "must_visit": [], "avoid": [], "meals": True,
            "profile": {"party_type": "solo", "pace": 2, "fitness": 2}}
HOUR_REASONS = {"gio an", "hop buoi toi", "vua suc", "mac dinh", "nang gat buoi trua"}


class TestExplanationsAndRepairReadTheValue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        by_id = {p["poi_id"]: p for p in DAY}
        ranked = [{"poi_id": pid, "reasons": ["gio an", "vua suc"]} for pid in by_id]
        cls.plans = {profile: profiles.build_plan(profile, DAY_TRIP, ranked, by_id, DAY_CELLS,
                                                  template="")
                     for profile in PROFILES}

    def test_every_stop_is_explained_by_its_value(self):
        for profile, plan in self.plans.items():
            self.assertTrue(plan["passed"], (profile, plan.get("violations")))
            for act in plan["activities"]:
                why = act["explanation"]
                self.assertEqual(why["source"], "value", profile)
                self.assertTrue(why["evidence"], (profile, act["poi_id"]))
                self.assertFalse(set(why["evidence"]) & HOUR_REASONS, why["evidence"])
                if act["poi_id"] in ("eatery", "bistro") and "11:00" <= act["start"] < "13:00":
                    self.assertIn("bua trua", why["evidence"])
        for act in self.plans["savings"]["activities"]:
            if act["poi_id"] in ("beach", "market", "temple"):
                self.assertIn("mien phi", act["explanation"]["evidence"])
        for act in self.plans["balanced"]["activities"]:
            if act["poi_id"] == "temple":
                self.assertIn("rating cao 4.9", act["explanation"]["evidence"])

    def test_repair_ranks_by_the_values_the_plan_was_made_with(self):
        plan = self.plans["savings"]
        values = repair._values(plan, DAY_TRIP, DAY)
        self.assertEqual({pid: values[pid] for pid in plan["_context"]["values"]},
                         plan["_context"]["values"])
        mine = repair._values({**plan, "_context": {**plan["_context"], "values": {"beach": 99.0}}},
                              DAY_TRIP, DAY)
        self.assertEqual(mine["beach"], 99.0)
        with mock.patch.dict(os.environ, {"DAVEL_OBJECTIVE": "legacy"}):
            self.assertIsNone(repair._values(plan, DAY_TRIP, DAY))


if __name__ == "__main__":
    unittest.main()
