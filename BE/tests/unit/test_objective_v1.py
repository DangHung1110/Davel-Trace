"""Objective v1 (BE/app/services/objective.py): formula, scenarios, monotonicity, gate.

Small synthetic days solved to optimality on one worker, so every assertion is about
the objective and not about the search budget.
"""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import replace
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from BE.app.services import objective  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.common import to_min  # noqa: E402

MEALS = ((10 * 60 + 30, 14 * 60), (17 * 60, 21 * 60))


def _poi(pid, group, zone, score, restaurant=False, visit=60, windows=None):
    wins = windows or ((7 * 60, 21 * 60),)
    return StubPOI(pid, visit_min=visit, open_min=wins[0][0], close_min=wins[-1][1],
                   score=score, restaurant=restaurant,
                   category="restaurant" if restaurant else group,
                   windows=tuple(wins) if len(wins) > 1 else (),
                   group="" if restaurant else group, zone=zone)


def _travel(pois, same=10, cross=30, extra=None):
    out = {}
    for a in pois:
        for b in pois:
            if a.poi_id != b.poi_id:
                out[(a.poi_id, b.poi_id)] = same if a.zone == b.zone else cross
    out.update(extra or {})
    return out


def _spec(**kw):
    base = dict(w=objective.weights("v1"), k0=6, pace=2, food_tour=False,
                strict=frozenset(), breakfast=False)
    base.update(kw)
    return objective.Spec(**base)


def _solve(pois, travel, spec, start=8 * 60, end=18 * 60, **kw):
    return optimize(pois, travel, StubTrip(start, end, origin_id=None), workers=1,
                    timeout_s=30, objective=spec, **kw)


def _ids(out):
    return [a["poi_id"] for a in out["itinerary"]["activities"]]


def _acts_min(out):
    return [{"poi_id": a["poi_id"], "start": to_min(a["start"])}
            for a in out["itinerary"]["activities"]]


def _day():
    pois = [
        _poi("beach1", "beach", "son_tra", 5.0),
        _poi("beach2", "beach", "son_tra", 4.8),
        _poi("beach3", "beach", "son_tra", 4.6),
        _poi("temple", "religious", "son_tra", 4.0),
        _poi("museum", "history", "trung_tam", 4.4),
        _poi("cafe", "cafe", "trung_tam", 3.0, visit=45),
        _poi("lunch1", "", "son_tra", 3.5, restaurant=True, windows=MEALS),
        _poi("lunch2", "", "trung_tam", 3.4, restaurant=True, windows=MEALS),
    ]
    return pois, _travel(pois)


class TestFormula(unittest.TestCase):
    def test_solver_objective_equals_feature_sum(self):
        pois, travel = _day()
        spec = _spec(k0=4)
        out = _solve(pois, travel, spec)
        self.assertEqual(out["status"], "optimal")
        stubs = {p.poi_id: p for p in pois}
        f = objective.features(_acts_min(out), stubs, travel, spec, 8 * 60, 18 * 60)
        model_u = out["objective"] / (1000.0 * out["unit"])
        self.assertAlmostEqual(model_u, objective.objective_value(f, spec), delta=0.01)

    def test_repeat_cost_is_submodular(self):
        spec = _spec()
        costs = [objective.repeat_cost(spec, "beach", c) for c in range(1, 5)]
        steps = [b - a for a, b in zip(costs, costs[1:])]
        self.assertEqual(costs[0], 0.0)
        self.assertTrue(all(b > a for a, b in zip(steps, steps[1:])))
        self.assertAlmostEqual(objective.repeat_cost(spec, "beach", 2), 1.5 * 0.35)

    def test_groups_from_the_snapshot_records(self):
        beach = {"poi_id": "x", "data_version": "2.1", "category": "beach", "name": "Mỹ Khê",
                 "dwell": {"p50": 90},
                 "provenance": {"dwell": {"source": "dwell_table_v2:beach"}}}
        food = {**beach, "category": "restaurant",
                "provenance": {"dwell": {"source": "dwell_table_v2:restaurant"}}}
        park = {**beach, "category": "paid_attraction", "name": "Sun World Ba Na Hills",
                "provenance": {"dwell": {"source": "category_rule+user_ok"}}}
        with mock.patch("BE.common.is_v21", return_value=True):
            self.assertEqual(objective.diversity_group(beach), "beach")
            self.assertEqual(objective.diversity_group(food), "")
            self.assertEqual(objective.diversity_group(park), "big_park")


class TestScenarios(unittest.TestCase):
    def test_no_third_beach(self):
        pois, travel = _day()
        out = _solve(pois, travel, _spec(k0=8))
        beaches = [p for p in _ids(out) if p.startswith("beach")]
        self.assertLessEqual(len(beaches), 2)

    def test_a_lunch_without_a_hard_rule(self):
        pois, travel = _day()
        out = _solve(pois, travel, _spec())
        starts = {a["poi_id"]: to_min(a["start"]) for a in out["itinerary"]["activities"]}
        self.assertTrue(any(pid.startswith("lunch") and 11 * 60 <= s < 13 * 60
                            for pid, s in starts.items()))

    def test_slow_pace_has_fewer_stops(self):
        pois, travel = _day()
        slow = _solve(pois, travel, _spec(k0=3))
        fast = _solve(pois, travel, _spec(k0=8))
        self.assertLess(len(_ids(slow)), len(_ids(fast)))

    def test_food_tour_may_stack_meals(self):
        pois = [_poi(f"food{i}", "", "trung_tam", 4.0, restaurant=True, visit=40,
                     windows=((7 * 60, 21 * 60),)) for i in range(4)]
        pois += [_poi("museum", "history", "trung_tam", 2.0)]
        travel = _travel(pois)
        plain = _solve(pois, travel, _spec(), start=10 * 60, end=15 * 60)
        tour = _solve(pois, travel, _spec(food_tour=True), start=10 * 60, end=15 * 60)
        count = lambda out: sum(1 for p in _ids(out) if p.startswith("food"))  # noqa: E731
        self.assertGreaterEqual(count(tour), 3)
        self.assertLess(count(plain), count(tour))

    def test_strict_a1_keeps_one_restaurant_per_meal(self):
        pois = [_poi(f"food{i}", "", "trung_tam", 4.0, restaurant=True, visit=40,
                     windows=((7 * 60, 21 * 60),)) for i in range(4)]
        travel = _travel(pois)
        out = _solve(pois, travel, _spec(food_tour=True, strict=frozenset({"A1"})),
                     start=10 * 60, end=15 * 60)
        lunch = [a for a in out["itinerary"]["activities"]
                 if 11 * 60 <= to_min(a["start"]) < 14 * 60]
        self.assertLessEqual(len(lunch), 1)

    def test_near_beats_far_at_equal_value(self):
        pois = [_poi("near", "history", "trung_tam", 4.0),
                _poi("far", "nature", "hai_van", 4.0),
                _poi("start", "religious", "trung_tam", 5.0)]
        travel = _travel(pois, same=10, cross=50)
        out = _solve(pois, travel, _spec(k0=2), start=8 * 60, end=11 * 60)
        ids = _ids(out)
        self.assertIn("near", ids)
        self.assertNotIn("far", ids)


class TestMonotone(unittest.TestCase):
    def _ride(self, out, travel):
        ids = _ids(out)
        return sum(travel[(a, b)] for a, b in zip(ids, ids[1:]))

    def test_more_weight_on_riding_never_rides_more(self):
        pois, travel = _day()
        base = _spec(k0=6)
        heavy = replace(base, w={**base.w, "tau": base.w["tau"] * 4, "zeta": base.w["zeta"] * 4})
        self.assertLessEqual(self._ride(_solve(pois, travel, heavy), travel),
                             self._ride(_solve(pois, travel, base), travel))

    def test_more_weight_on_repeats_never_repeats_more(self):
        pois, travel = _day()
        base = _spec(k0=8)
        heavy = replace(base, w={**base.w, "repeat_scale": 4.0})
        beaches = lambda out: sum(1 for p in _ids(out) if p.startswith("beach"))  # noqa: E731
        self.assertLessEqual(beaches(_solve(pois, travel, heavy)),
                             beaches(_solve(pois, travel, base)))


class TestGateUnderV1(unittest.TestCase):
    def test_taste_rules_widen_and_strict_rules_harden(self):
        from BE.app.services import soft_rules
        with mock.patch.dict(os.environ, {"DAVEL_OBJECTIVE": "v1"}):
            self.assertIn("CAFE_CAP", soft_rules.taste_rules())
            self.assertIn("REST_FOLLOWS_LUNCH",
                          soft_rules.soft_checks(frozenset(), {"strict_rules": ["A1"]}))
            self.assertNotIn("A1", soft_rules.soft_checks(frozenset(), {"strict_rules": ["A1"]}))
        with mock.patch.dict(os.environ, {"DAVEL_OBJECTIVE": "legacy"}):
            self.assertNotIn("CAFE_CAP", soft_rules.taste_rules())

    def test_lunch_stays_hard(self):
        from BE.app.services import gate
        trip = {"start_time": "08:00", "end_time": "18:00", "profile": {"pace": 2}}
        pois = {"m": {"poi_id": "m", "cat": "museum", "type": "museum"}}
        no_lunch = {"activities": [{"poi_id": "m", "start": "11:00", "end": "13:30"}]}
        self.assertFalse(gate.check_lunch(no_lunch, trip, pois, {})["passed"])
        self.assertTrue(gate.check_lunch(no_lunch, {**trip, "profile": {}}, pois, {})["passed"])


if __name__ == "__main__":
    unittest.main()
