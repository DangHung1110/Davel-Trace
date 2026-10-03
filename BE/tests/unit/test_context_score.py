"""Unit test for context scorer (T023). Fixture-based.

Covers: dating/quiet/sea query ranks the right POI first with fired
rules; post-hiking prefers recovery types.

Run from repo root: python BE/tests/unit/test_context_score.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.context_score import score_context  # noqa: E402

COVE = {"poi_id": "cove", "type": "beach", "rating": 4.6, "intensity": 1,
        "ambience": "yên tĩnh", "crowd": "vừa phải", "tags": ["biển", "hẹn hò"]}
CLUB = {"poi_id": "club", "type": "landmark", "rating": 3.5, "intensity": 3,
        "ambience": "ồn ào", "crowd": "đông", "tags": ["nhạc"]}
HILL = {"poi_id": "hill", "type": "nature", "rating": 4.7, "intensity": 3,
        "ambience": "hoang sơ", "crowd": "", "tags": ["leo núi"]}

QUERY = ["yên tĩnh", "hẹn hò", "gần biển"]


class TestContextScore(unittest.TestCase):
    def test_query_ranks_right_poi(self):
        cove = score_context(COVE, QUERY)
        club = score_context(CLUB, QUERY)
        self.assertGreater(cove["score"], club["score"])
        self.assertEqual([f["rule"] for f in cove["fired"]],
                         ["quiet", "dating", "near_sea"])
        self.assertTrue(all("reason" in f for f in cove["fired"]))

    def test_recovery_after_hiking(self):
        beach = score_context(COVE, ["sau leo núi, mệt"])
        hill = score_context(HILL, ["sau leo núi, mệt"])
        self.assertGreater(beach["score"], hill["score"])
        self.assertIn("recovery", [f["rule"] for f in beach["fired"]])

    def test_neutral_without_keywords(self):
        r = score_context(CLUB, ["đi chơi"])
        self.assertEqual(r, {"score": 0.5, "fired": []})

    def test_scores_bounded(self):
        for poi in (COVE, CLUB, HILL):
            s = score_context(poi, QUERY)["score"]
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)


if __name__ == "__main__":
    unittest.main()
