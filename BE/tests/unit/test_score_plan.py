"""Unit test for plan scorer (T032s, lane B). Profit/Utility + gate.

Preference-heavy ask -> experience top utility; tight budget ->
savings top profit; gate-failed plan excluded.

Run from repo root: python BE/tests/unit/test_score_plan.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.profiles import run_profiles, score_plan  # noqa: E402

CS1 = {"FAR": 1, "VROH": 1, "B3": 1, "BCS": 1}
EXP = {"profile": "experience", "total_cost": 500000, "travel_min": 60,
       "preference": 4.8, "constraint_status": dict(CS1)}
SAV = {"profile": "savings", "total_cost": 0, "travel_min": 120,
       "preference": 4.2, "constraint_status": dict(CS1)}
BAD = {"profile": "balanced", "total_cost": 100000, "travel_min": 60,
       "preference": 4.5,
       "constraint_status": {"FAR": 1, "VROH": 0, "B3": 1, "BCS": 1}}


class TestScorePlan(unittest.TestCase):
    def test_preference_heavy_experience_top_utility(self):
        self.assertGreater(score_plan(EXP)["utility"], score_plan(SAV)["utility"])
        print(f"\n utility exp {score_plan(EXP)['utility']} > sav {score_plan(SAV)['utility']}")

    def test_tight_budget_savings_top_profit(self):
        self.assertGreater(score_plan(SAV)["profit"], score_plan(EXP)["profit"])
        print(f"\n profit sav {score_plan(SAV)['profit']} > exp {score_plan(EXP)['profit']}")

    def test_gate_fail_excluded(self):
        r = score_plan(BAD)
        self.assertFalse(r["gate"])
        self.assertTrue(r["excluded"])
        self.assertEqual((r["profit"], r["utility"]), (0.0, 0.0))

    def test_pool_profit_winner_is_savings(self):
        from BE.tests.unit.test_profiles import IDS, MATRIX, POIS, TRAVEL, TRIP
        pool = run_profiles(POIS, TRAVEL, TRIP, MATRIX)
        scored = [(p["profile"], score_plan(p)) for p in pool["plans"]]
        self.assertTrue(all(s["gate"] for _, s in scored))
        winner = max(scored, key=lambda ps: ps[1]["profit"])[0]
        self.assertEqual(winner, "savings")


if __name__ == "__main__":
    unittest.main()
