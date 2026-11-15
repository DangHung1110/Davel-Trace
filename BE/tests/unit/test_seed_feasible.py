"""The solver's seed is a feasible day of the model, or it is made one.

A search on a budget of work starts from the greedy seed (`optimizer._greedy_hint`).
A seed the model rejects leaves the search to find its first day alone, and on the
largest days (friends, 11 stops, late end) it did not inside the budget: 3 of 9 such
solves returned nothing and the traveller got an EMPTY plan. Two rules of the model
were unknown to the walk:

- a template's late end (one visit ends at or after 20:00): the walk spent the money
  and the day's one landmark by noon, and its last stop ended at 19:17;
- the two-cafe rule (one before 11:00 AND one after 13:00): a first cafe at 12:45 is
  in neither daypart, yet a second one was seated at 16:36.

The walk now knows both. A seed still rejected for another reason costs nothing while
the search finds a day alone; when it finds none, a second search that starts by
repairing the seed is the rescue (`_repair_hint`).

Run: python -m pytest BE/tests/unit/test_seed_feasible.py -q
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from ortools.sat.python import cp_model  # noqa: E402

from BE.app.services import optimizer as optimizer_mod  # noqa: E402
from BE.app.services.optimizer import (  # noqa: E402
    StubPOI, StubTrip, _closers, _ending_late, _greedy_hint, _late_span, optimize)

H = 60
LATE = 20 * H


def stub(pid, category, visit=60, opens=8 * H, closes=22 * H, score=4.0, fee=0, windows=()):
    return StubPOI(pid, visit_min=visit, open_min=opens, close_min=closes, score=score,
                   restaurant=category == "restaurant", category=category, fee=fee, windows=windows)


def flat(pois, minutes=10):
    return {(a.poi_id, b.poi_id): minutes for a in pois for b in pois if a is not b}


def seated(pois, hint):
    return {pois[i - 1].poi_id: start for i, start in hint}


class TestTwoCafeRule(unittest.TestCase):
    CAFES = [stub("cafe_a", "cafe", visit=45, opens=7 * H), stub("cafe_b", "cafe", visit=45, opens=16 * H),
             stub("museum", "museum", closes=17 * H)]

    def _cafes(self, start_min):
        hint = _greedy_hint(self.CAFES, flat(self.CAFES), StubTrip(start_min, 20 * H, None), set(),
                            cafe_cap=2, no_consecutive=True)
        return sorted(start for pid, start in seated(self.CAFES, hint).items() if pid.startswith("cafe"))

    def test_a_morning_and_an_afternoon_cafe_are_seated(self):
        cafes = self._cafes(8 * H)
        self.assertEqual(len(cafes), 2)
        self.assertLess(cafes[0], 11 * H)
        self.assertGreater(cafes[1], 13 * H)

    def test_a_first_cafe_at_lunch_time_gets_no_second(self):
        # 12:00 is neither daypart: the model allows one cafe only on such a day.
        cafes = self._cafes(12 * H)
        self.assertEqual(len(cafes), 1, cafes)


class TestLateEnd(unittest.TestCase):
    def test_late_span(self):
        bridge = stub("bridge", "landmark", visit=20, opens=0, closes=24 * H)
        trip = StubTrip(8 * H, 22 * H, None)
        self.assertEqual(_late_span(bridge, LATE, trip), (19 * H + 40, 21 * H + 40))
        self.assertIsNone(_late_span(stub("museum", "museum", closes=17 * H), LATE, trip))
        self.assertIsNone(_late_span(bridge, None, trip))

    def test_the_last_stop_is_moved_later_inside_its_hours(self):
        dinner = stub("dinner", "restaurant", opens=17 * H, closes=22 * H)
        trip = StubTrip(17 * H, 22 * H, None)
        self.assertEqual(_ending_late(dinner, 17 * H + 30, LATE, trip, None), 19 * H)
        # Already late, or held to an hour by a wish: it stays.
        self.assertIsNone(_ending_late(dinner, 19 * H + 30, LATE, trip, None))
        self.assertIsNone(_ending_late(dinner, 17 * H + 30, LATE, trip, None, timed={1}, node=1))
        # Closing at 19:30 it cannot end at 20:00.
        early = stub("early", "restaurant", visit=30, opens=17 * H, closes=19 * H + 30)
        self.assertIsNone(_ending_late(early, 18 * H, LATE, trip, None))

    def test_a_dinner_is_not_moved_out_of_its_meal(self):
        # 21:00 would end late and be no dinner (the dinner window closes at 20:30).
        long_dinner = stub("dinner", "restaurant", visit=30, opens=17 * H, closes=23 * H)
        later = _ending_late(long_dinner, 18 * H, 21 * H + 30, StubTrip(17 * H, 23 * H, None), None)
        self.assertIsNone(later)

    def test_the_walk_ends_late_when_only_the_dinner_can(self):
        pois = [stub("museum", "museum", closes=17 * H), stub("dinner", "restaurant", opens=17 * H)]
        hint = _greedy_hint(pois, flat(pois), StubTrip(15 * H, 22 * H, None), set(),
                            dinner_required=True, late_end_min=LATE)
        self.assertGreaterEqual(seated(pois, hint)["dinner"] + 60, LATE)

    # The friends day of the audit in small: one landmark a day, a dinner that closes
    # at 19:30. Walked as before, the bridge is seen in the morning and nothing can end late.
    DAY = [stub("bridge", "landmark", visit=20, opens=0, closes=24 * H, score=5.0),
           stub("museum", "museum", closes=17 * H),
           stub("park", "park", visit=45, opens=5 * H, closes=18 * H),
           stub("market", "market", opens=14 * H, closes=19 * H),
           stub("lunch", "restaurant", visit=40, windows=((10 * H + 30, 15 * H), (17 * H, 19 * H + 30)),
                opens=10 * H + 30, closes=19 * H + 30),
           stub("dinner", "restaurant", visit=30, windows=((10 * H + 30, 15 * H), (17 * H, 19 * H + 30)),
                opens=10 * H + 30, closes=19 * H + 30)]
    RULES = dict(category_cap=1, no_consecutive=True, no_adjacent_food=True, lunch_required=True,
                 dinner_required=True)

    def _walk(self, pois=None, **extra):
        pois = pois or self.DAY
        hint = _greedy_hint(pois, flat(pois), StubTrip(8 * H, 22 * H, None), set(),
                            **{**self.RULES, **extra})
        return pois, hint

    def test_without_a_late_end_the_bridge_is_a_morning_stop(self):
        pois, hint = self._walk()
        self.assertLess(seated(pois, hint)["bridge"], 12 * H)

    def test_an_evening_stop_is_kept_back_when_the_day_must_end_late(self):
        pois, hint = self._walk(late_end_min=LATE)
        places = seated(pois, hint)
        self.assertGreaterEqual(places["bridge"] + 20, LATE, places)
        # The day is still a whole day: both meals, and the stops that fit before them.
        self.assertEqual(set(places), {"bridge", "museum", "park", "market", "lunch", "dinner"})

    def test_its_fee_is_held_for_it(self):
        # 300 a person: a paid museum in the morning would leave no money for the bar,
        # the only stop that can end late.
        pois = [stub("museum", "museum", closes=17 * H, fee=150, score=5.0),
                stub("bar", "bar", visit=90, opens=19 * H, closes=24 * H, fee=200),
                stub("park", "park", visit=45, opens=5 * H, closes=18 * H),
                stub("market", "market", opens=14 * H, closes=19 * H),
                stub("lunch", "restaurant", visit=40, opens=10 * H + 30, closes=15 * H, fee=50),
                stub("dinner", "restaurant", visit=30, opens=17 * H, closes=19 * H + 30, fee=50)]
        _, blind = self._walk(pois, max_fee=300)
        self.assertIn("museum", seated(pois, blind))
        self.assertNotIn("bar", seated(pois, blind))
        _, hint = self._walk(pois, max_fee=300, late_end_min=LATE)
        places = seated(pois, hint)
        self.assertGreaterEqual(places["bar"] + 90, LATE, places)
        self.assertLessEqual(sum(p.fee for p in pois if p.poi_id in places), 300)

    def test_closers_are_evening_stops_that_are_no_meal_and_not_named(self):
        trip = StubTrip(8 * H, 22 * H, None)
        order = _closers(self.DAY, LATE, trip, set(), set(), None, None, 0, lambda poi, start: 0.0)
        self.assertEqual([self.DAY[i - 1].poi_id for i in order], ["bridge"])
        named = _closers(self.DAY, LATE, trip, set(), {"bridge"}, None, None, 0, lambda poi, start: 0.0)
        self.assertEqual(named, [])

    def test_a_day_that_already_ends_late_is_walked_once(self):
        pois = self.DAY + [stub("bar", "bar", visit=90, opens=19 * H, closes=24 * H)]
        with mock.patch.object(optimizer_mod, "_closers", side_effect=AssertionError("not needed")):
            _, hint = self._walk(pois, late_end_min=LATE)
        self.assertTrue(any(start + pois[i - 1].visit_min >= LATE for i, start in hint))

    def test_the_solver_takes_such_a_seed_as_its_first_day(self):
        seeds = []
        real = optimizer_mod._complete_hint

        def spy(model, module):
            seeds.append(real(model, module))
            return seeds[-1]

        with mock.patch.object(optimizer_mod, "_complete_hint", spy):
            out = optimize(self.DAY, flat(self.DAY), StubTrip(8 * H, 22 * H, None), workers=1,
                           deterministic_time=2.0, late_end_min=LATE, **self.RULES)
        self.assertEqual(len(seeds), 1)
        self.assertIsNotNone(seeds[0], "the model rejected the seed")
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        ends = [int(a["end"][:2]) * H + int(a["end"][3:]) for a in out["itinerary"]["activities"]]
        self.assertGreaterEqual(max(ends), LATE)


class TestRescueOfASearchWithNoSeed(unittest.TestCase):
    POIS = [stub("a", "park", score=2.0), stub("b", "museum", score=1.0), stub("c", "market", score=1.5)]
    TRIP = StubTrip(8 * H, 18 * H, None)

    @staticmethod
    def _bad_seed(*_args, **_kwargs):
        return [(1, 8 * H), (2, 8 * H)]      # b starts while a is still being visited

    def test_a_rejected_seed_costs_nothing_while_the_search_finds_a_day(self):
        with mock.patch.object(optimizer_mod, "_greedy_hint", self._bad_seed), \
                mock.patch.object(optimizer_mod, "_repair_hint", side_effect=AssertionError("not needed")):
            out = optimize(self.POIS, flat(self.POIS), self.TRIP, workers=1, deterministic_time=1.5)
        self.assertEqual(out["status"], "optimal")
        self.assertFalse(out["rescued"])

    def test_a_search_that_found_nothing_is_run_again_from_the_repaired_seed(self):
        real = cp_model.CpSolver.Solve
        budgets = []

        def plain_search_finds_nothing(solver, model, *args, **kwargs):
            if solver.parameters.repair_hint:
                budgets.append(solver.parameters.max_deterministic_time)
            probe = solver.parameters.fix_variables_to_their_hinted_value or solver.parameters.repair_hint
            return real(solver, model, *args, **kwargs) if probe else cp_model.UNKNOWN

        with mock.patch.object(optimizer_mod, "_greedy_hint", self._bad_seed), \
                mock.patch.object(cp_model.CpSolver, "Solve", plain_search_finds_nothing):
            out = optimize(self.POIS, flat(self.POIS), self.TRIP, workers=1, deterministic_time=1.5)
        self.assertEqual(budgets, [1.5])                      # the search's own budget, once
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        self.assertTrue(out["rescued"])
        acts = out["itinerary"]["activities"]
        self.assertEqual(len(acts), 3)                        # the best day, not just any
        for before, after in zip(acts, acts[1:]):
            self.assertLessEqual(before["end"], after["start"])

    def test_with_nothing_to_repair_the_answer_stays_unknown(self):
        def finds_nothing(solver, model, *args, **kwargs):
            return cp_model.UNKNOWN

        with mock.patch.object(optimizer_mod, "_greedy_hint", lambda *a, **k: []), \
                mock.patch.object(cp_model.CpSolver, "Solve", finds_nothing):
            out = optimize(self.POIS, flat(self.POIS), self.TRIP, workers=1, deterministic_time=1.5)
        self.assertEqual(out["status"], "unknown")

    def test_a_wall_clock_search_is_left_as_it_was(self):
        def finds_nothing(solver, model, *args, **kwargs):
            self.assertFalse(solver.parameters.repair_hint)
            return cp_model.UNKNOWN

        with mock.patch.object(optimizer_mod, "_greedy_hint", self._bad_seed), \
                mock.patch.object(cp_model.CpSolver, "Solve", finds_nothing):
            out = optimize(self.POIS, flat(self.POIS), self.TRIP, workers=1)
        self.assertEqual(out["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
