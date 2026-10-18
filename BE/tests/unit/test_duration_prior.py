"""Dwell duration prior tests (T064 M2, lane A). Math + hooks, no gold needed.

Real eval (coverage >=80%, MAE >=10% better) waits for the user gold
checklist — PENDING, see docs/dwell-prior.md. These tests lock the
shrinkage behavior and phase-PR hooks.

Run from repo root: python BE/tests/unit/test_duration_prior.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.patm.duration_prior import (  # noqa: E402
    SHRINK_K,
    get_p50,
    get_p75,
    load,
    shrink,
)
from BE.ml.patm.estimate_duration import CATEGORY_DEFAULTS  # noqa: E402


class TestDurationPrior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior = load()

    def test_ten_cats_monotonic(self):
        self.assertEqual(len(self.prior["cats"]), len(CATEGORY_DEFAULTS))
        for cat, v in self.prior["cats"].items():
            self.assertLessEqual(v["p25"], v["p50"], cat)
            self.assertLessEqual(v["p50"], v["p75"], cat)
            self.assertIn(v["confidence"], ("low", "medium", "high"))
            self.assertGreaterEqual(v["n"], 0)

    def test_shrinkage_toward_default(self):
        self.assertEqual(shrink("restaurant", {"p25": 1, "p50": 1, "p75": 1}, 0),
                         {"p25": 42.0, "p50": 60.0, "p75": 84.0})
        post = shrink("restaurant", {"p25": 10, "p50": 30, "p75": 60}, 100)
        self.assertGreater(post["p50"], 30.0)  # pulled up toward 60
        self.assertLess(post["p50"], 60.0)
        self.assertEqual(SHRINK_K, 20)

    def test_hooks_with_fallback(self):
        self.assertGreater(get_p50("restaurant"), 0)
        self.assertGreater(get_p75("restaurant"), get_p50("restaurant"))
        self.assertEqual(get_p50("nope-cat"), 60.0)  # nac-1 fallback
        self.assertEqual(get_p75("nope-cat"), 84.0)

    def test_empty_cats_fall_back_clean(self):
        beach = self.prior["cats"]["beach"]
        self.assertEqual(beach["n"], 0)
        self.assertEqual(beach["p50"], 120.0)


if __name__ == "__main__":
    unittest.main()
