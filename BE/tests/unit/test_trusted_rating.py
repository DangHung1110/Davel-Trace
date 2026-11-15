"""Rating shrunk by review count, and the fame term of the balanced profile.

Run from repo root: python -m pytest BE/tests/unit/test_trusted_rating.py -q
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.profiles import _score  # noqa: E402
from BE.app.services.rank import score_poi  # noqa: E402
from BE.common import RATING_PRIOR, trusted_rating  # noqa: E402

SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "snapshots" / "danang-v1"


def poi(rating, reviews=None):
    out = {"poi_id": "p", "rating": rating, "cat": "landmark"}
    if reviews is not None:
        out["review_count"] = reviews
    return out


class TestTrustedRating(unittest.TestCase):
    def test_unknown_count_keeps_the_raw_rating(self):
        self.assertEqual(trusted_rating(poi(4.2)), 4.2)

    def test_no_rating_stays_zero(self):
        self.assertEqual(trusted_rating(poi(None)), 0.0)
        self.assertEqual(trusted_rating(poi(None, 50)), 0.0)

    def test_few_reviews_say_little(self):
        self.assertAlmostEqual(trusted_rating(poi(5.0, 2)), RATING_PRIOR, delta=0.01)
        self.assertEqual(trusted_rating(poi(5.0, 0)), RATING_PRIOR)

    def test_many_reviews_keep_their_rating(self):
        self.assertAlmostEqual(trusted_rating(poi(4.9, 10262)), 4.9, delta=0.01)
        self.assertLess(trusted_rating(poi(5.0, 13)), trusted_rating(poi(4.9, 10262)))


class TestBalancedScore(unittest.TestCase):
    def test_a_known_place_beats_an_anecdotal_five(self):
        self.assertGreater(_score("balanced", poi(4.5, 16325)), _score("balanced", poi(5.0, 13)))

    def test_fame_does_not_rescue_a_bad_place(self):
        self.assertLess(_score("balanced", poi(3.5, 5000)), _score("balanced", poi(4.9, 200)))

    def test_no_count_scores_the_raw_rating(self):
        self.assertEqual(_score("balanced", poi(4.2)), 4.2)


class TestRankReason(unittest.TestCase):
    def test_few_reviews_are_not_called_high_rating(self):
        reasons = score_poi(poi(5.0, 2))["reasons"]
        self.assertFalse([r for r in reasons if r.startswith("rating cao")], reasons)
        self.assertIn("rating cao 4.8", score_poi(poi(4.8, 1466))["reasons"])
        self.assertIn("rating cao 4.8", score_poi(poi(4.8))["reasons"])


class TestRealSnapshot(unittest.TestCase):
    def test_every_rated_verified_poi_has_a_count(self):
        pois = json.loads((SNAPSHOT / "pois.json").read_text(encoding="utf-8"))["pois"]
        missing = [p["name"] for p in pois
                   if p.get("verified") and p.get("rating") is not None
                   and p.get("review_count") is None]
        # without a count trusted_rating falls back to the raw rating, and the
        # POI outranks every place whose rating was shrunk
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
