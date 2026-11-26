"""J's features read off a finished day (`objective.features`): the gaps of the review.

Until 26/11 `features` took T2 (time-of-day state and rain) and T7 (the siesta) from
its caller, which no caller had for a finished plan, and counted only restaurant
pairs under 2.5 h while the solver's A2 charges every pair. So its J was not what
CP-SAT maximised, and it could not describe the day a judge sees (`profiles._polished`
re-times the solver's day). Every solver-parity test below fails on that version.
Small synthetic days solved to optimality on one worker, like test_objective_v1.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from BE.app.services import objective  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.common import to_min  # noqa: E402

MEALS = ((10 * 60 + 30, 14 * 60), (17 * 60, 21 * 60))
BANDS = [(8 * 60, 12 * 60), (12 * 60, 18 * 60)]


def _poi(pid, group, zone, score, restaurant=False, visit=60, windows=None, booking=False):
    wins = windows or ((7 * 60, 21 * 60),)
    return StubPOI(pid, visit_min=visit, open_min=wins[0][0], close_min=wins[-1][1],
                   score=score, restaurant=restaurant,
                   category="restaurant" if restaurant else group,
                   windows=tuple(wins) if len(wins) > 1 else (),
                   group="" if restaurant else group, zone=zone, booking=booking)


def _travel(pois, same=10, cross=30):
    return {(a.poi_id, b.poi_id): same if a.zone == b.zone else cross
            for a in pois for b in pois if a.poi_id != b.poi_id}


def _spec(**kw):
    base = dict(w=objective.weights("v1"), k0=6, pace=2, food_tour=False,
                strict=frozenset(), breakfast=False)
    base.update(kw)
    return objective.Spec(**base)


def _solve(pois, travel, spec, start=8 * 60, end=18 * 60, **kw):
    out = optimize(pois, travel, StubTrip(start, end, origin_id=None), workers=1,
                   timeout_s=30, objective=spec, **kw)
    assert out["status"] == "optimal", out.get("status")
    return out


def _acts_min(out):
    return [{"poi_id": a["poi_id"], "start": to_min(a["start"])}
            for a in out["itinerary"]["activities"]]


def _model_j(out):
    return out["objective"] / (1000.0 * out["unit"])


def _wet_day():
    pois = [
        _poi("museum", "history", "trung_tam", 4.0),
        _poi("beach", "beach", "son_tra", 5.0),
        _poi("view", "viewpoint", "son_tra", 3.0, windows=((13 * 60, 17 * 60),)),
        _poi("lunch", "", "trung_tam", 3.5, restaurant=True, windows=MEALS),
    ]
    scores = {("museum", 0): 1.2, ("museum", 1): 0.9, ("beach", 0): 1.1, ("beach", 1): 0.6,
              ("view", 0): 1.0, ("view", 1): 1.0}
    costs = {("beach", 1): 1.2, ("view", 1): 1.2}    # the afternoon is wet
    return pois, _travel(pois), scores, costs


class TestStateAndRain(unittest.TestCase):
    def _check(self, spec):
        pois, travel, scores, costs = _wet_day()
        out = _solve(pois, travel, spec, must_visit=["view"], state_bands=BANDS,
                     state_score=scores, state_cost=costs)
        f = objective.features(_acts_min(out), {p.poi_id: p for p in pois}, travel, spec,
                               8 * 60, 18 * 60, bands=BANDS, state_scores=scores,
                               state_costs=costs)
        self.assertGreater(f["rain"], 0.0)       # the must-visit viewpoint is open air
        self.assertNotEqual(f["state"], 0.0)
        self.assertAlmostEqual(_model_j(out), objective.objective_value(f, spec), delta=0.01)

    def test_solver_objective_equals_features_with_state_and_rain(self):
        self._check(_spec(k0=4))

    def test_the_solver_reads_the_rain_weight(self):
        self._check(_spec(k0=4, w={**objective.weights("v1"), "w_rain": 0.25}))

    def test_a_weights_file_without_w_rain_keeps_the_old_rain_cost(self):
        w = {k: v for k, v in objective.weights("v1").items() if k != "w_rain"}
        self.assertEqual(_spec(w=w).rain_weight(), 1.0)


class TestSiesta(unittest.TestCase):
    def _day(self):
        pois = [
            _poi("temple", "religious", "son_tra", 4.0),
            _poi("museum", "history", "trung_tam", 4.4),
            _poi("cafe", "cafe", "trung_tam", 2.0, visit=45),
            _poi("lunch", "", "trung_tam", 3.5, restaurant=True, windows=MEALS),
        ]
        return pois, _travel(pois)

    def test_solver_objective_equals_features_with_a_siesta(self):
        pois, travel = self._day()
        spec = _spec(k0=3, pace=1)
        out = _solve(pois, travel, spec, rest_after_lunch=60)
        self.assertTrue(out["rest_taken"])
        f = objective.features(_acts_min(out), {p.poi_id: p for p in pois}, travel, spec,
                               8 * 60, 18 * 60, rest_minutes=60)
        self.assertGreater(f["rest"], 0.0)
        self.assertAlmostEqual(_model_j(out), objective.objective_value(f, spec), delta=0.01)

    def test_a_stop_inside_the_siesta_ends_it(self):
        pois, travel = self._day()
        stubs = {p.poi_id: p for p in pois}
        spec = _spec(k0=3, pace=1)
        free = [{"poi_id": "museum", "start": 9 * 60}, {"poi_id": "lunch", "start": 12 * 60},
                {"poi_id": "temple", "start": 14 * 60 + 10}]
        busy = free[:2] + [{"poi_id": "temple", "start": 13 * 60 + 30}]
        rest = [objective.features(acts, stubs, travel, spec, 8 * 60, 18 * 60,
                                   rest_minutes=60)["rest"] for acts in (free, busy)]
        self.assertGreater(rest[0], 0.0)
        self.assertEqual(rest[1], 0.0)

    def test_a_strict_siesta_is_a_constraint_not_a_bonus(self):
        pois, travel = self._day()
        spec = _spec(k0=3, pace=1, strict=frozenset({"REST_FOLLOWS_LUNCH"}))
        acts = [{"poi_id": "museum", "start": 9 * 60}, {"poi_id": "lunch", "start": 12 * 60},
                {"poi_id": "temple", "start": 14 * 60 + 10}]
        f = objective.features(acts, {p.poi_id: p for p in pois}, travel, spec,
                               8 * 60, 18 * 60, rest_minutes=60)
        self.assertEqual(f["rest"], 0.0)


class TestMealPairs(unittest.TestCase):
    def test_lunch_and_dinner_pay_what_the_solver_charges(self):
        pois = [
            _poi("museum", "history", "trung_tam", 4.4),
            _poi("bridge", "outdoor_urban", "trung_tam", 3.0, visit=30),
            _poi("lunch", "", "trung_tam", 3.5, restaurant=True, windows=MEALS),
            _poi("dinner", "", "trung_tam", 3.4, restaurant=True, windows=MEALS),
        ]
        travel = _travel(pois)
        spec = _spec(k0=4)
        out = _solve(pois, travel, spec, end=21 * 60, must_visit=["lunch", "dinner"])
        f = objective.features(_acts_min(out), {p.poi_id: p for p in pois}, travel, spec,
                               8 * 60, 21 * 60)
        self.assertEqual(f["meal_far"], 1.0)     # the two meals are hours apart
        self.assertAlmostEqual(_model_j(out), objective.objective_value(f, spec), delta=0.01)

    def test_a_class_is_the_meal_of_the_slot_it_overlaps(self):
        pois = [
            _poi("class", "cooking_class", "trung_tam", 4.0, visit=150,
                 windows=((9 * 60, 11 * 60 + 30),), booking=True),
            _poi("lunch", "", "trung_tam", 3.5, restaurant=True,
                 windows=((12 * 60, 13 * 60 + 30),)),
            _poi("museum", "history", "trung_tam", 4.4),
        ]
        travel = _travel(pois)
        spec = _spec(k0=4)
        out = _solve(pois, travel, spec, must_visit=["class", "lunch"])
        f = objective.features(_acts_min(out), {p.poi_id: p for p in pois}, travel, spec,
                               8 * 60, 18 * 60)
        self.assertEqual(f["meal_crowd"], 1.0)   # 09:00-11:30 class + 12:00 lunch, one slot
        self.assertAlmostEqual(_model_j(out), objective.objective_value(f, spec), delta=0.01)


class TestShownTimes(unittest.TestCase):
    def test_features_follow_the_times_a_plan_shows(self):
        stubs = {p.poi_id: p for p in (_poi("museum", "history", "trung_tam", 4.0),
                                        _poi("dinner", "", "trung_tam", 3.5, restaurant=True,
                                             windows=MEALS))}
        travel = _travel(list(stubs.values()))
        scores = {("museum", 0): 1.2, ("museum", 1): 0.7}
        spec = _spec()
        solver = [{"poi_id": "museum", "start": 10 * 60}, {"poi_id": "dinner", "start": 17 * 60 + 40}]
        shown = [{"poi_id": "museum", "start": 15 * 60 + 30}, {"poi_id": "dinner", "start": 17 * 60 + 20}]
        raw, seen = (objective.features(acts, stubs, travel, spec, 8 * 60, 21 * 60,
                                        bands=BANDS, state_scores=scores)
                     for acts in (solver, shown))
        self.assertGreater(raw["meal"], seen["meal"])     # 17:20 is before the dinner window
        self.assertGreater(raw["state"], seen["state"])   # the museum left its good band

    def test_shown_acts_reads_a_plan(self):
        acts = objective.shown_acts([{"poi_id": "a", "start": "09:15", "end": "10:00"},
                                     {"kind": "note"}, {"poi_id": "b", "start": 600}])
        self.assertEqual(acts, [{"poi_id": "a", "start": 555}, {"poi_id": "b", "start": 600}])

    def test_features_name_every_term_once(self):
        self.assertEqual(len(objective.FEATURES), len(set(objective.FEATURES)))
        stubs = {"a": _poi("a", "beach", "son_tra", 1.0)}
        f = objective.features([{"poi_id": "a", "start": 9 * 60}], stubs, {}, _spec(),
                               8 * 60, 18 * 60)
        self.assertEqual(set(f), set(objective.FEATURES))


class TestIdleMinutes(unittest.TestCase):
    """`wait` (step 2b): idle minutes between stops, measured for the pilot only."""

    def _day(self):
        pois = [_poi("museum", "history", "trung_tam", 4.0),
                _poi("lunch", "", "trung_tam", 3.5, restaurant=True, windows=MEALS),
                _poi("temple", "religious", "trung_tam", 3.0)]
        return {p.poi_id: p for p in pois}, _travel(pois)  # 10-minute legs, one zone

    def test_a_hole_before_lunch_is_idle_the_ride_and_the_overhead_are_not(self):
        stubs, travel = self._day()
        # museum 09:00-10:00, then 10 minutes of riding + the 12-minute stop overhead
        acts = [{"poi_id": "museum", "start": 9 * 60}, {"poi_id": "lunch", "start": 11 * 60}]
        self.assertEqual(objective.idle_minutes(acts, stubs, travel), 38)
        tight = [acts[0], {"poi_id": "lunch", "start": 10 * 60 + 22}]
        self.assertEqual(objective.idle_minutes(tight, stubs, travel), 0)

    def test_the_siesta_after_lunch_is_not_idle(self):
        stubs, travel = self._day()
        acts = [{"poi_id": "lunch", "start": 12 * 60}, {"poi_id": "temple", "start": 14 * 60 + 10}]
        self.assertEqual(objective.idle_minutes(acts, stubs, travel, rest_minutes=60), 10)
        self.assertEqual(objective.idle_minutes(acts, stubs, travel), 48)

    def test_waiting_is_measured_not_charged(self):
        stubs, travel = self._day()
        spec = _spec()
        acts = [{"poi_id": "museum", "start": 9 * 60}, {"poi_id": "lunch", "start": 11 * 60}]
        f = objective.features(acts, stubs, travel, spec, 8 * 60, 18 * 60)
        self.assertEqual(f["wait"], 38)
        self.assertEqual(spec.coef("w_wait"), 0.0)
        self.assertEqual(objective.objective_value(f, spec),
                         objective.objective_value({**f, "wait": 0.0}, spec))


if __name__ == "__main__":
    unittest.main()
