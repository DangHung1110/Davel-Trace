"""Objective v1 T11 (BE/app/services/objective.py): near-duplicate stops.

A day that rides less packs close stops, and the closest are often one place under
two records. T11 charges them on the day (not on adjacent legs), so a stop slipped
in between does not escape. Small synthetic days solved to optimality.
"""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import replace
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from BE.app.services import objective, rules  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.common import to_min  # noqa: E402

MEALS = ((10 * 60 + 30, 14 * 60), (17 * 60, 21 * 60))


def _poi(pid, group, score, visit=60, restaurant=False, windows=None, **keys):
    wins = windows or ((7 * 60, 21 * 60),)
    return StubPOI(pid, visit_min=visit, open_min=wins[0][0], close_min=wins[-1][1],
                   score=score, restaurant=restaurant,
                   category="restaurant" if restaurant else group,
                   windows=tuple(wins) if len(wins) > 1 else (),
                   group="" if restaurant else group, zone="z", **keys)


def _travel(pois, minutes=10):
    return {(a.poi_id, b.poi_id): minutes for a in pois for b in pois if a.poi_id != b.poi_id}


def _spec(**kw):
    base = dict(w=objective.weights("v1"), k0=8, pace=2, food_tour=False,
                strict=frozenset(), breakfast=False)
    base.update(kw)
    return objective.Spec(**base)


def _solve(pois, spec, start=8 * 60, end=17 * 60):
    travel = _travel(pois)
    out = optimize(pois, travel, StubTrip(start, end, origin_id=None), workers=1,
                   timeout_s=30, objective=spec)
    return out, travel


def _ids(out):
    return [a["poi_id"] for a in out["itinerary"]["activities"]]


def _v21(pid, name, category, kind, **extra):
    return {"poi_id": pid, "data_version": "2.1", "name": name, "category": category,
            "provenance": {"dwell": {"source": f"dwell_table_v2:{kind}"}}, **extra}


class TestKeys(unittest.TestCase):
    """The keys come from the snapshot fields, not from hand lists."""

    def test_site_area_market_and_dish(self):
        area = _v21("old", "Phố cổ Hội An", "paid_attraction", "old_town",
                    alt_group="hoi_an_old_town_walk")
        hall = _v21("hall", "Hội quán Phúc Kiến", "religious", "religious",
                    requires_ticket_of="old")
        market = _v21("han", "Chợ Hàn", "day_market", "market")
        night = _v21("helio", "Chợ đêm Helio", "night_market", "night_market")
        noodle = _v21("mq", "Mì Quảng Bà Mua", "restaurant", "restaurant")
        with mock.patch("BE.common.is_v21", return_value=True):
            self.assertEqual(objective.stub_keys(area)["site"], "alt:hoi_an_old_town_walk")
            # the parent's alt_group names the area: any record of it is an umbrella
            self.assertEqual(objective.stub_keys(hall, area)["inside"], "alt:hoi_an_old_town_walk")
            self.assertEqual(objective.stub_keys(hall)["inside"], "old")
            self.assertEqual(objective.stub_keys(market)["substitute"], "day_market")
            self.assertEqual(objective.stub_keys(night)["substitute"], "")
            self.assertEqual(objective.stub_keys(noodle)["dish"], "mi_quang")
            self.assertEqual(objective.stub_keys(market)["dish"], "")

    def test_dish_reads_the_sourced_label_first(self):
        # tags.dishes (BE.common.DISHES, with a source) beats the name; the runtime
        # view carries the display names in `dishes`; the name is the fallback.
        record = {"poi_id": "r", "category": "restaurant", "name": "Quán Bà Ba",
                  "tags": {"dishes": [{"dish": "mi_quang", "source": "web"}]}}
        view = {"poi_id": "r", "cat": "restaurant", "name": "Quán Bà Ba", "dishes": ["mì Quảng"]}
        named = {"poi_id": "r", "cat": "restaurant", "name": "Bánh Xèo Bà Dưỡng"}
        self.assertEqual(objective.dish_of(record), "mi_quang")
        self.assertEqual(objective.dish_of(view), "mi_quang")
        self.assertEqual(objective.dish_of(named), "banh_xeo")
        self.assertEqual(objective.dish_of({"cat": "cafe", "name": "Mì Quảng cafe"}), "")
        # a diet is no dish: two vegetarian meals are not a repeat
        veg = {"poi_id": "v", "category": "restaurant", "name": "Quán Chay Sen",
               "tags": {"dishes": [{"dish": "mon_chay"}]}}
        self.assertEqual(objective.dish_of(veg), "")

    def test_parent_by_poi_id_or_osm_ref(self):
        area = {"poi_id": "ChIJarea", "ext_ids": {"osm": "node/42"}}
        by_id = {"ChIJarea": area}
        self.assertIs(objective.parent_of({"requires_ticket_of": "ChIJarea"}, by_id), area)
        self.assertIs(objective.parent_of({"requires_ticket_of": "osm:node/42"}, by_id), area)
        self.assertIsNone(objective.parent_of({"requires_ticket_of": "osm:node/7"}, by_id))

    def test_counts_on_the_day(self):
        stubs = [_poi("pass", "viewpoint", 1, site="alt:hai_van"),
                 _poi("gate", "experience", 1, site="alt:hai_van"),
                 _poi("old", "history", 1, site="alt:walk"),
                 _poi("hall1", "religious", 1, inside="alt:walk"),
                 _poi("hall2", "religious", 1, inside="alt:walk"),
                 _poi("han", "market", 1, substitute="day_market"),
                 _poi("con", "market", 1, substitute="day_market"),
                 _poi("mq1", "", 1, restaurant=True, dish="mi_quang"),
                 _poi("mq2", "", 1, restaurant=True, dish="mi_quang")]
        self.assertEqual(objective.duplicate_counts(stubs),
                         {"same_site": 1.0, "umbrella": 2.0, "market": 1.0, "dish": 1.0})
        # two stops inside the area and no area stop: free
        self.assertEqual(objective.duplicate_counts(stubs[3:5])["umbrella"], 0.0)

    def test_rules_are_taste_terms(self):
        for name in ("SAME_SITE", "MARKET_REPEAT", "SAME_DISH"):
            self.assertEqual(rules.layer(name), "taste")
            self.assertEqual(rules.term(name), "T11")
            self.assertIn(name, objective.STRICTABLE)


class TestSolver(unittest.TestCase):
    """Without T11 the solver takes both records; with it, one, unless worth it."""

    def _no_dup(self):
        w = dict(objective.weights("v1"))
        for key in ("dup_same_site", "dup_umbrella", "dup_market", "dup_dish"):
            w[key] = 0.0
        return _spec(w=w)

    def test_same_site_once(self):
        pois = [_poi("pass", "viewpoint", 5.0, site="alt:hai_van"),
                _poi("gate", "experience", 4.8, site="alt:hai_van"),
                _poi("beach", "beach", 2.0)]
        both, _ = _solve(pois, self._no_dup())
        self.assertTrue({"pass", "gate"} <= set(_ids(both)))
        out, _ = _solve(pois, _spec())
        self.assertEqual(len({"pass", "gate"} & set(_ids(out))), 1)

    def test_area_and_a_stop_inside_it(self):
        pois = [_poi("old", "history", 5.0, site="alt:walk"),
                _poi("hall", "religious", 4.8, inside="alt:walk"),
                _poi("beach", "beach", 2.0)]
        out, _ = _solve(pois, _spec())
        self.assertEqual(len({"old", "hall"} & set(_ids(out))), 1)
        # two stops inside the area, no area stop: both stay
        pois2 = [_poi("hall", "religious", 4.8, inside="alt:walk"),
                 _poi("house", "history", 4.6, inside="alt:walk")]
        out2, _ = _solve(pois2, _spec())
        self.assertEqual(set(_ids(out2)), {"hall", "house"})

    def test_second_market_even_with_a_stop_between(self):
        pois = [_poi("con", "market", 5.0, substitute="day_market"),
                _poi("han", "market", 4.9, substitute="day_market"),
                _poi("church", "religious", 4.0)]
        out, _ = _solve(pois, _spec())
        self.assertEqual(len({"con", "han"} & set(_ids(out))), 1)
        tour, _ = _solve(pois, _spec(food_tour=True))
        self.assertTrue({"con", "han"} <= set(_ids(tour)))

    def test_same_dish_at_lunch_and_dinner(self):
        pois = [_poi("mq1", "", 5.0, restaurant=True, windows=MEALS, dish="mi_quang"),
                _poi("mq2", "", 4.9, restaurant=True, windows=MEALS, dish="mi_quang"),
                _poi("other", "", 3.0, restaurant=True, windows=MEALS),
                _poi("beach", "beach", 4.0)]
        out, _ = _solve(pois, _spec(), end=20 * 60 + 30)
        ids = set(_ids(out))
        self.assertLessEqual(len({"mq1", "mq2"} & ids), 1)
        self.assertIn("other", ids)

    def test_greedy_seed_skips_duplicates(self):
        # A 5-unit search often kept its seed: the seed must not hand it Chợ Hàn +
        # Chợ Cồn or one place twice. A food tour keeps both markets in the seed.
        from BE.app.services.optimizer import _greedy_hint, _hint_dup_kinds
        pois = [_poi("con", "market", 5.0, substitute="day_market"),
                _poi("han", "market", 4.9, substitute="day_market"),
                _poi("pass", "viewpoint", 4.8, site="alt:hai_van"),
                _poi("gate", "experience", 4.7, site="alt:hai_van")]
        trip = StubTrip(8 * 60, 17 * 60, origin_id=None)
        seed = _greedy_hint(pois, _travel(pois), trip, set(),
                            dup_free=_hint_dup_kinds(_spec()))
        ids = {pois[i - 1].poi_id for i, _start in seed}
        self.assertEqual(len(ids & {"con", "han"}), 1)
        self.assertEqual(len(ids & {"pass", "gate"}), 1)
        tour = _greedy_hint(pois, _travel(pois), trip, set(),
                            dup_free=_hint_dup_kinds(_spec(food_tour=True)))
        self.assertTrue({"con", "han"} <= {pois[i - 1].poi_id for i, _s in tour})
        self.assertEqual(_hint_dup_kinds(None), frozenset())  # legacy: seed unchanged

    def test_strict_makes_it_a_constraint(self):
        pois = [_poi("pass", "viewpoint", 5.0, site="alt:hai_van"),
                _poi("gate", "experience", 4.8, site="alt:hai_van")]
        w = dict(objective.weights("v1"), dup_same_site=0.0)
        out, _ = _solve(pois, _spec(w=w, strict=frozenset({"SAME_SITE"})))
        self.assertEqual(len(_ids(out)), 1)

    def test_solver_objective_equals_feature_sum(self):
        pois = [_poi("pass", "viewpoint", 5.0, site="alt:hai_van"),
                _poi("gate", "experience", 4.9, site="alt:hai_van"),
                _poi("con", "market", 3.0, substitute="day_market"),
                _poi("han", "market", 2.9, substitute="day_market"),
                _poi("old", "history", 1.5, site="alt:walk"),
                _poi("hall", "religious", 1.4, inside="alt:walk")]
        w = dict(objective.weights("v1"), dup_same_site=0.1, dup_market=0.1, dup_umbrella=0.1)
        spec = _spec(w=w)
        out, travel = _solve(pois, spec)
        self.assertEqual(out["status"], "optimal")
        acts = [{"poi_id": a["poi_id"], "start": to_min(a["start"])}
                for a in out["itinerary"]["activities"]]
        f = objective.features(acts, {p.poi_id: p for p in pois}, travel, spec, 8 * 60, 17 * 60)
        self.assertGreater(f["same_site"] + f["market"] + f["umbrella"], 0)
        model_u = out["objective"] / (1000.0 * out["unit"])
        self.assertAlmostEqual(model_u, objective.objective_value(f, spec), delta=0.01)



class TestPaceCountsSights(unittest.TestCase):
    """T8 counts sights, not meals: a day at its comfortable count still eats dinner."""

    def test_k0_less_the_meal_windows(self):
        spec = _spec(k0=8)
        self.assertEqual(objective.sight_k0(spec, 8 * 60, 21 * 60), 6)   # lunch + dinner
        self.assertEqual(objective.sight_k0(spec, 13 * 60, 16 * 60), 8)  # no meal window
        # a day to 18:00 cannot eat dinner (window 17:30-20:30): no sight is held for it
        self.assertEqual(objective.sight_k0(spec, 8 * 60, 18 * 60), 7)

    def test_dinner_is_not_a_pace_stop(self):
        sights = [_poi(f"s{i}", g, 4.0 - 0.1 * i, visit=50)
                  for i, g in enumerate(("beach", "religious", "history", "nature"))]
        meals = [_poi("lunch", "", 2.0, restaurant=True, windows=MEALS, dish="a"),
                 _poi("dinner", "", 2.0, restaurant=True, windows=MEALS, dish="b")]
        spec = _spec(k0=6)      # 6 - lunch - dinner = 4 sights
        out, _ = _solve(sights + meals, spec, end=20 * 60 + 30)
        ids = set(_ids(out))
        self.assertTrue({"lunch", "dinner"} <= ids, ids)
        self.assertEqual(len(ids - {"lunch", "dinner"}), 4)

    def test_a_third_restaurant_pays_the_pace(self):
        spec = _spec(k0=8)
        day = (8 * 60, 21 * 60)                       # lunch + dinner windows
        self.assertEqual(objective.paced_stops(6, 2, spec, *day), 6)
        self.assertEqual(objective.paced_stops(6, 3, spec, *day), 7)
        # a 07:00 start opens a breakfast window: it gives no free meal to the pace
        early = _spec(k0=8, breakfast=True)
        self.assertEqual(objective.paced_stops(5, 3, early, 7 * 60, 21 * 60), 6)


if __name__ == "__main__":
    unittest.main()
