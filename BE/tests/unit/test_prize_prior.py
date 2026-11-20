"""prize_prior: clean popularity (category + guides + Michelin + signature)."""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

from migrate_v2 import CATEGORY_PRIOR, prize_prior  # noqa: E402


def pp(cat="restaurant", sig=False, mentions=0, michelin=False):
    return prize_prior(cat, sig, None, None, None, mentions, michelin)[0]


class TestPrizePrior(unittest.TestCase):
    def test_no_guide_is_category_prior_not_a_penalty(self):
        self.assertEqual(pp(), CATEGORY_PRIOR["restaurant"])

    def test_more_guides_rank_higher_and_saturate(self):
        vals = [pp(mentions=k) for k in (0, 1, 3, 15)]
        self.assertEqual(vals, sorted(vals))
        self.assertLessEqual(vals[-1] - vals[0], 0.3 + 1e-9)

    def test_michelin_and_signature(self):
        self.assertGreater(pp(mentions=3, michelin=True), pp(mentions=3))
        self.assertGreaterEqual(pp(cat="beach", sig=True), 0.9)

    def test_bounded(self):
        self.assertLessEqual(pp(cat="beach", sig=True, mentions=50, michelin=True), 1.0)

    def test_guides_mark_source(self):
        _, by, _, note = prize_prior("cafe", False, None, None, None, 2, False)
        self.assertEqual(by, "open_data")
        self.assertIn("guides=2", note)


if __name__ == "__main__":
    unittest.main()
