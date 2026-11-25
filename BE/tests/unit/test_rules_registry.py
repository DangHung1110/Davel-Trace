"""The one book of rules (BE/app/services/rules.py): every rule has one layer, and the
gate, soft_rules, objective and scorer read their sets from it."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from BE.app.services import gate, objective, rules, scorer, soft_rules  # noqa: E402


class TestRegistry(unittest.TestCase):
    def test_every_rule_has_a_layer(self):
        for name, _fn in gate.CHECKS:
            self.assertIn(name, rules.RULES, name)
        for name in gate.RULE_FREEZE:
            self.assertIn(name, rules.RULES, name)
        for name in rules.HCS_MIRROR:
            self.assertIn(rules.layer(name), {"physical", "user", "taste"}, name)

    def test_sets_come_from_the_registry(self):
        self.assertEqual(gate.SOFT_CHECKS, frozenset({"F1", "TIME_FIT", "DINNER"}))
        self.assertEqual(gate.SOFT_CHECKS, rules.QUALITY)
        self.assertEqual(soft_rules.TASTE_RULES, frozenset({"CATEGORY_CAP", "NO_CONSECUTIVE"}))
        self.assertEqual(soft_rules.V1_TASTE_RULES, rules.TASTE)
        self.assertEqual(objective.STRICTABLE, rules.TASTE)

    def test_every_taste_rule_names_its_objective_term(self):
        for name in rules.TASTE | rules.EDGE:
            self.assertRegex(rules.term(name) or "", r"^T\d+$", name)


class TestOnePlacePerRule(unittest.TestCase):
    """Under objective v1 the edges carry the transition score only."""

    def test_edges_drop_the_rule_penalties_on_request(self):
        pois = {"r1": {"poi_id": "r1", "cat": "restaurant"},
                "r2": {"poi_id": "r2", "cat": "restaurant"}}
        with mock.patch.object(scorer, "_ensure_model", return_value=False):
            with_rules = scorer.edge_scores(["r1", "r2"], pois)
            plain = scorer.edge_scores(["r1", "r2"], pois, rule_penalties=False)
        penalty = soft_rules.edge_penalty(pois["r1"], pois["r2"])
        self.assertLess(penalty, 0)
        self.assertAlmostEqual(with_rules[("r1", "r2")] - plain[("r1", "r2")], penalty, places=3)

    def test_profiles_are_three_weight_sets_of_one_objective(self):
        base = objective.build_spec({"start_time": "08:00", "end_time": "18:00"})
        exp = objective.build_spec({"start_time": "08:00", "end_time": "18:00"},
                                   profile="experience")
        self.assertEqual(base.coef("repeat_scale"), 1.0)
        self.assertEqual(exp.coef("repeat_scale"), 2.5)
        self.assertEqual(exp.coef("tau"), base.coef("tau"))


if __name__ == "__main__":
    unittest.main()
