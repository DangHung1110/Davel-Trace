"""exp/soft-rules-v2: CATEGORY_CAP and NO_CONSECUTIVE are soft by default.

- soft_rules.solver_taste_args: soft penalties by default, hard when the trip asks
  (`strict_rules`) or DAVEL_TASTE_RULES=hard (the old behaviour);
- gate/validator: a soft taste rule is reported (`soft_failed`/`soft_violations`)
  and never fails the plan, HCS included;
- optimizer: with the soft cap a second market is chosen only when it is worth more
  than the penalty;
- retrieval: "phố cổ" means the Hội An old town cluster.

Run: python -m pytest BE/tests/unit/test_soft_taste_rules.py -q
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import retrieval, soft_rules  # noqa: E402
from BE.app.services.gate import report  # noqa: E402
from BE.app.services.validator import validate  # noqa: E402

TRIP = {"budget": 3000000, "start_time": "07:00", "end_time": "19:00"}
POIS = {"m1": {"verified": True, "cat": "market", "fee": 0, "opening_hours": ["00:00-23:59"]},
        "m2": {"verified": True, "cat": "market", "fee": 0, "opening_hours": ["00:00-23:59"]}}
MATRIX = {"m1->m2": {"minutes": 10}}
TWO_MARKETS = {"activities": [{"poi_id": "m1", "start": "08:00", "end": "09:00"},
                              {"poi_id": "m2", "start": "10:00", "end": "11:00"}]}


@mock.patch.dict(os.environ, {"DAVEL_TASTE_RULES": "soft"})
class TestTasteArgs(unittest.TestCase):
    def test_default_is_soft(self):
        args = soft_rules.solver_taste_args(TRIP)
        self.assertIsNone(args["category_cap"])
        self.assertEqual(args["soft_category_cap"], soft_rules.CATEGORY_DAILY_CAP)
        self.assertFalse(args["no_consecutive"])
        self.assertTrue(args["soft_no_consecutive"])

    def test_traveller_can_make_a_rule_hard(self):
        trip = dict(TRIP, strict_rules=["category_cap"])
        args = soft_rules.solver_taste_args(trip)
        self.assertEqual(args["category_cap"], soft_rules.CATEGORY_DAILY_CAP)
        self.assertIsNone(args["soft_category_cap"])
        self.assertTrue(args["soft_no_consecutive"])  # the other rule stays soft

    @mock.patch.dict(os.environ, {"DAVEL_OBJECTIVE": "legacy"})  # legacy hard-rule behaviour
    def test_env_restores_the_old_hard_rules(self):
        with mock.patch.dict(os.environ, {"DAVEL_TASTE_RULES": "hard"}):
            self.assertEqual(soft_rules.taste_rules_hard(TRIP), soft_rules.TASTE_RULES)


@mock.patch.dict(os.environ, {"DAVEL_TASTE_RULES": "soft"})
class TestGateReportsSoftRules(unittest.TestCase):
    def test_two_markets_are_reported_not_failed(self):
        rep = report(TWO_MARKETS, TRIP, POIS, MATRIX)
        self.assertNotIn("CATEGORY_CAP", rep["failed"])
        self.assertNotIn("HCS", rep["failed"])
        self.assertIn("CATEGORY_CAP", rep["soft_failed"])
        val = validate(TWO_MARKETS, TRIP, POIS, MATRIX)
        self.assertIn("CATEGORY_CAP", val["soft_violations"])
        self.assertNotIn("HCS", val["violations"])

    def test_soft_rule_does_not_fail_its_gate_family(self):
        from BE.app.modules.planning_lifecycle.stable_planner import family_report
        fam = family_report(report(TWO_MARKETS, TRIP, POIS, MATRIX))["families"]
        traveler = fam["traveler_constraints"]
        self.assertTrue(traveler["passed"])
        row = next(c for c in traveler["checks"] if c["check"] == "CATEGORY_CAP")
        self.assertTrue(row["soft_failed"])

    def test_strict_trip_fails_closed(self):
        trip = dict(TRIP, strict_rules=["CATEGORY_CAP"])
        rep = report(TWO_MARKETS, trip, POIS, MATRIX)
        self.assertIn("CATEGORY_CAP", rep["failed"])
        self.assertIn("HCS", rep["failed"])


class TestPhoCoWish(unittest.TestCase):
    def test_pho_co_is_the_old_town_cluster(self):
        old_town = {"poi_id": "a", "name": "Hội quán Phúc Kiến", "cat": "temple",
                    "cluster_id": "hoi_an_old_town"}
        elsewhere = {"poi_id": "b", "name": "Chùa Linh Ứng", "cat": "temple",
                     "cluster_id": None}
        self.assertTrue(retrieval.poi_fits_wish(old_town, "phố cổ"))
        self.assertTrue(retrieval.poi_fits_wish(old_town, "đi phố cổ Hội An"))
        self.assertFalse(retrieval.poi_fits_wish(elsewhere, "phố cổ"))
        self.assertTrue(retrieval.match_activity("phố cổ"))


if __name__ == "__main__":
    unittest.main()
