"""A search that runs out of budget is not an infeasible model.

CP-SAT answers UNKNOWN when the work budget ends before any solution; the old
code reported that as `infeasible`, so the template ladder paid the full budget
on every rung left and then ran the rule-by-rule diagnosis on top (a minute of
solving for an empty plan). Now the solver says `unknown`, the ladder stops after
MAX_UNKNOWN_RUNGS such rungs, and the plan names the budget, not a rule.

Run: python -m pytest BE/tests/unit/test_search_budget.py -q
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from ortools.sat.python import cp_model  # noqa: E402

from BE.app.services import optimizer as optimizer_mod  # noqa: E402
from BE.app.services import profiles as profiles_mod  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.app.services.profiles import build_plan  # noqa: E402
from BE.tests.unit.test_template_wiring import BY_ID, CELLS, RANKED, _trip  # noqa: E402

H = 60
POIS = [StubPOI("a", visit_min=60, open_min=8 * H, close_min=18 * H, score=2.0),
        StubPOI("b", visit_min=60, open_min=8 * H, close_min=18 * H, score=1.0)]
TRAVEL = {("a", "b"): 10, ("b", "a"): 10, ("depot", "a"): 5, ("depot", "b"): 5,
          ("a", "depot"): 5, ("b", "depot"): 5}


def _solve_unknown(self, model, callback=None):
    return cp_model.UNKNOWN


class TestOptimizerStatus(unittest.TestCase):
    def test_budget_exhausted_is_unknown_not_infeasible(self):
        with mock.patch.object(cp_model.CpSolver, "Solve", _solve_unknown):
            out = optimize(POIS, TRAVEL, StubTrip(8 * H, 18 * H, "depot"),
                           workers=1, deterministic_time=0.1)
        self.assertEqual(out["status"], "unknown")
        self.assertIsNone(out["itinerary"])
        self.assertIn("ngan sach", out["reason"])

    def test_a_real_solve_still_reports_optimal(self):
        out = optimize(POIS, TRAVEL, StubTrip(8 * H, 18 * H, "depot"), workers=1)
        self.assertEqual(out["status"], "optimal")


class TestSearchSettings(unittest.TestCase):
    """A search on a budget of work runs CP-SAT with one presolve pass and light
    probing: the default presolve spent half the budget before the search began
    (72 real models: 98.2 % of the best value at 8 units against 99.3 % at 5)."""

    def _parameters(self, **kwargs):
        seen = []
        real = cp_model.CpSolver.Solve

        def spy(solver, model, *args, **more):
            if not solver.parameters.fix_variables_to_their_hinted_value:
                seen.append((solver.parameters.max_presolve_iterations,
                             solver.parameters.cp_model_probing_level,
                             solver.parameters.num_search_workers))
            return real(solver, model, *args, **more)

        with mock.patch.object(cp_model.CpSolver, "Solve", spy):
            out = optimize(POIS, TRAVEL, StubTrip(8 * H, 18 * H, "depot"), **kwargs)
        self.assertEqual(out["status"], "optimal")
        return seen[-1]

    def test_a_budget_of_work_uses_the_light_presolve(self):
        presolve, probing, workers = self._parameters(deterministic_time=1.0)
        self.assertEqual((presolve, probing, workers),
                         (optimizer_mod.SEARCH_PRESOLVE_ITERATIONS, optimizer_mod.SEARCH_PROBING_LEVEL, 1))
        self.assertEqual((presolve, probing), (1, 1))

    def test_a_wall_clock_search_keeps_the_solver_defaults(self):
        presolve, probing, _workers = self._parameters()
        defaults = cp_model.CpSolver().parameters
        self.assertEqual((presolve, probing),
                         (defaults.max_presolve_iterations, defaults.cp_model_probing_level))


class TestLadderStopsOnBudget(unittest.TestCase):
    def test_ladder_stops_and_names_the_budget(self):
        calls = []

        def unknown(*args, **kwargs):
            calls.append(kwargs)
            return {"status": "unknown", "itinerary": None,
                    "reason": "solver het ngan sach truoc khi tim duoc lich (UNKNOWN)",
                    "elapsed_s": 0.0}

        with mock.patch.object(profiles_mod, "optimize", unknown):
            plan = build_plan("balanced", _trip("08:00", "18:00"), RANKED, BY_ID, CELLS,
                              template="family-slow", workers=1, deterministic_time=1.0)
        self.assertEqual(len(calls), profiles_mod.MAX_UNKNOWN_RUNGS)  # no diagnosis solves
        self.assertEqual(plan["activities"], [])
        self.assertFalse(plan["passed"])
        self.assertEqual(plan["infeasible_by"]["rule"], "SEARCH_BUDGET")
        self.assertTrue(any("ngan sach" in w for w in plan["warnings"]), plan["warnings"])

    def test_a_wish_the_budget_cannot_seat_is_dropped_not_the_day(self):
        # "cáp treo" (a seven-hour park) could not sit next to lunch and dinner: the
        # wished rungs ran out of budget and the traveller got no plan at all.
        calls = []
        real = optimizer_mod.optimize

        def unknown_while_wished(*args, **kwargs):
            calls.append(kwargs)
            if any(group.get("poi_ids") for group in kwargs.get("required_any") or []):
                return {"status": "unknown", "itinerary": None,
                        "reason": "solver het ngan sach truoc khi tim duoc lich (UNKNOWN)",
                        "elapsed_s": 0.0}
            return real(*args, **kwargs)

        with mock.patch.object(profiles_mod, "optimize", unknown_while_wished):
            plan = build_plan("balanced", _trip("08:00", "18:00", activities=["bảo tàng"]),
                              RANKED, BY_ID, CELLS, template="family-slow", workers=1)
        wished = [c for c in calls if any(g.get("poi_ids") for g in c.get("required_any") or [])]
        self.assertEqual(len(wished), profiles_mod.MAX_UNKNOWN_RUNGS)  # the rest are skipped
        self.assertTrue(plan["activities"])
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertNotIn("infeasible_by", plan)
        # The day no longer has to hold the wish; it is reported either way.
        self.assertIn(plan["activity_match"][0]["status"], ("met", "unmet"))

    def test_a_proven_infeasible_rung_keeps_climbing(self):
        calls = []
        real = optimizer_mod.optimize

        def infeasible_then_real(*args, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return {"status": "infeasible", "itinerary": None,
                        "reason": "solver INFEASIBLE", "elapsed_s": 0.0}
            return real(*args, **kwargs)

        with mock.patch.object(profiles_mod, "optimize", infeasible_then_real):
            plan = build_plan("balanced", _trip("08:00", "18:00"), RANKED, BY_ID, CELLS,
                              template="family-slow", workers=1)
        self.assertGreater(len(calls), 1)
        self.assertTrue(plan["activities"])


if __name__ == "__main__":
    unittest.main()


WISH_POIS = [StubPOI("park", visit_min=60, open_min=6 * H, close_min=22 * H, score=3.0,
                     category="park"),
             StubPOI("r_plain", visit_min=60, open_min=10 * H, close_min=22 * H, score=5.0,
                     restaurant=True, category="restaurant"),
             StubPOI("r_named", visit_min=60, open_min=10 * H, close_min=22 * H, score=1.0,
                     restaurant=True, category="restaurant"),
             StubPOI("museum", visit_min=60, open_min=8 * H, close_min=17 * H, score=2.0,
                     category="museum")]
WISH_TRAVEL = {(a.poi_id, b.poi_id): 10 for a in WISH_POIS for b in WISH_POIS if a is not b}


class TestHintClosesNamedWish(unittest.TestCase):
    """A wish that names its places is a hard group in the wished rungs: the seed
    must seat one of THOSE at a meal, not the best-scoring restaurant."""

    POIS = WISH_POIS
    TRAVEL = WISH_TRAVEL
    GROUP = [{"count": 1, "categories": ["restaurant"], "poi_ids": ["r_named"]}]

    def _lunch(self, groups):
        """The restaurant the seed sits down to lunch at."""
        from BE.app.services.optimizer import _greedy_hint
        from BE.app.services.soft_rules import LUNCH_REQUIRED
        trip = StubTrip(8 * H, 20 * H, None)  # open tour, like the planner
        hint = _greedy_hint(self.POIS, self.TRAVEL, trip, set(), required_any=groups,
                            lunch_required=True, no_consecutive=True, no_adjacent_food=True)
        return [self.POIS[i - 1].poi_id for i, start in hint
                if self.POIS[i - 1].restaurant and LUNCH_REQUIRED[0] <= start < LUNCH_REQUIRED[1]]

    def test_named_restaurant_takes_the_meal(self):
        self.assertEqual(self._lunch(self.GROUP), ["r_named"])

    def test_without_a_named_group_the_best_restaurant_still_wins(self):
        self.assertEqual(self._lunch([{"count": 1, "categories": ["restaurant"]}]), ["r_plain"])

    def test_the_solver_takes_the_seed_as_its_first_solution(self):
        out = optimize(self.POIS, self.TRAVEL, StubTrip(8 * H, 20 * H, None), workers=1,
                       required_any=self.GROUP, lunch_required=True, deterministic_time=4.0)
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        self.assertIn("r_named", [a["poi_id"] for a in out["itinerary"]["activities"]])
