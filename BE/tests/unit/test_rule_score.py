"""Unit test for nac-1 rule scorer (T027). Stdlib unittest, seed-based.

Run from repo root: python BE/tests/unit/test_rule_score.py -v
"""

import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.patm import make_pairs  # noqa: E402
from BE.ml.patm.make_pairs import label_ordered, load_pois  # noqa: E402
from BE.ml.patm.rule_score import (  # noqa: E402
    TIE_MARGIN,
    explain_transition,
    predict,
    score_transition,
)

SNAPSHOT_DIR = os.path.join("data", "snapshots", "danang-v1")


class TestRuleScore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pois = list(load_pois(SNAPSHOT_DIR))

    def test_flip_exact_antisymmetry(self):
        for a, b in itertools.permutations(self.pois, 2):
            self.assertEqual(score_transition(b, a), -score_transition(a, b),
                             f"{a['poi_id']}/{b['poi_id']}")

    def test_matches_legacy_builder_rules(self):
        """Delegated scorer reproduces legacy margins/rules (backward compat)."""
        for a, b in itertools.permutations(self.pois, 2):
            legacy_margin, legacy_fired = make_pairs._legacy_margin(a, b)
            self.assertEqual(score_transition(a, b), round(legacy_margin, 3))
            self.assertEqual(explain_transition(a, b), legacy_fired)

    def test_builder_labels_come_from_scorer(self):
        for a, b in itertools.permutations(self.pois, 2):
            lab = label_ordered(a, b)
            self.assertEqual(lab["label"], predict(a, b))
            self.assertAlmostEqual(lab["margin"], score_transition(a, b))

    def test_tie_band(self):
        same = dict(self.pois[0])
        self.assertEqual(score_transition(same, dict(self.pois[0])), 0.0)
        self.assertEqual(predict(same, dict(self.pois[0])), 0)
        self.assertLessEqual(abs(score_transition(self.pois[0], self.pois[0])),
                             TIE_MARGIN)

    def test_known_preference_direction(self):
        by_id = {p["poi_id"]: p for p in self.pois}
        # spec US3: hiking (son-tra, intensity 3) before beach (my-khe, 2)
        self.assertEqual(predict(by_id["son-tra"], by_id["my-khe"]), 1)


if __name__ == "__main__":
    unittest.main()
