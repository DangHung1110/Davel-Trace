"""Unit test for rule ranker (T016). Fixture-based.

Covers: matching POI outranks opposite; weights sane; scores in [0,1].

Run from repo root: python BE/tests/unit/test_rank.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.rank import WEIGHTS, rank, score_poi  # noqa: E402

DATING_QUIET_SEA = {
    "poi_id": "cove", "type": "beach", "fee": 0, "rating": 4.6,
    "intensity": 1, "weather_sensitive": True,
    "tags": ["yên tĩnh", "hẹn hò", "biển"], "ambience": "yên tĩnh", "cuisine": [],
}
NOISY_CROWDED = {
    "poi_id": "club", "type": "landmark", "fee": 500000, "rating": 3.5,
    "intensity": 3, "weather_sensitive": False,
    "tags": ["ồn ào", "đông"], "ambience": "ồn ào", "cuisine": [],
}
USER = {"budget": 3000000, "fitness": 1,
        "food_prefs": ["hải sản"], "activities": ["yên tĩnh", "hẹn hò", "biển"]}
CTX = {"hour": "19:00", "rain_prob": 0.0}


class TestRank(unittest.TestCase):
    def test_match_outranks_opposite(self):
        ordered = rank([NOISY_CROWDED, DATING_QUIET_SEA], USER, CTX)
        self.assertEqual(ordered[0]["poi_id"], "cove")
        self.assertGreater(ordered[0]["score"], ordered[1]["score"])
        print(f"\n cove {ordered[0]['score']} > club {ordered[1]['score']}")

    def test_weights_sane(self):
        self.assertTrue(all(v >= 0 for v in WEIGHTS.values()))
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0)
        self.assertEqual(set(WEIGHTS),
                         {"rating", "price", "effort", "pref_match", "taste",
                          "time_fit", "weather", "fame"})

    def test_scores_bounded_with_reasons(self):
        for poi in (DATING_QUIET_SEA, NOISY_CROWDED):
            r = score_poi(poi, USER, CTX)
            self.assertGreaterEqual(r["score"], 0.0)
            self.assertLessEqual(r["score"], 1.0)
            self.assertTrue(r["reasons"])

    def test_rain_penalizes_outdoor(self):
        dry = score_poi(DATING_QUIET_SEA, USER, CTX)["score"]
        wet = score_poi(DATING_QUIET_SEA, USER,
                        {**CTX, "rain_prob": 0.9})["score"]
        self.assertGreater(dry, wet)

    def test_e2_nightlife_before_17h_is_penalized(self):
        """E2: a bar in the morning loses time_fit vs the same bar at night."""
        bar = {"poi_id": "bar", "cat": "bar", "type": "Quán bar", "fee": 0,
               "rating": 4.6, "intensity": 2, "tags": ["bar"], "ambience": ""}
        morning = score_poi(bar, {}, {"hour": "09:00"})
        evening = score_poi(bar, {}, {"hour": "19:00"})
        self.assertLess(morning["score"], evening["score"])
        self.assertIn("bar/ nightlife truoc 17h", " | ".join(morning["reasons"]))

    def test_c1_food_prefs_raise_taste_match(self):
        """C1: rank reads food_prefs (the router now forwards them)."""
        seafood = {"poi_id": "sea", "cat": "restaurant",
                   "type": "Nhà hàng hải sản", "fee": 0, "rating": 4.5,
                   "intensity": 1, "tags": ["Nhà hàng hải sản", "Hải sản"],
                   "ambience": ""}
        plain = {"poi_id": "plain", "cat": "restaurant",
                 "type": "Nhà hàng chay", "fee": 0, "rating": 4.5,
                 "intensity": 1, "tags": ["Nhà hàng chay"], "ambience": ""}
        user = {"food_prefs": ["hải sản"]}
        ctx = {"hour": "12:00"}
        self.assertGreater(score_poi(seafood, user, ctx)["score"],
                           score_poi(plain, user, ctx)["score"])

    def test_onboarding_outdoor_bias_moves_outdoor_pois(self):
        """Profile outdoor_bias (-1..1) is consumed: + prefers, - avoids."""
        beach = {"poi_id": "beach", "cat": "beach", "type": "Bãi biển",
                 "fee": 0, "rating": 4.5, "intensity": 1,
                 "weather_sensitive": True, "tags": ["biển"]}
        ctx = {"hour": "09:00"}
        self.assertGreater(score_poi(beach, {"outdoor_bias": 1.0}, ctx)["score"],
                           score_poi(beach, {"outdoor_bias": -1.0}, ctx)["score"])
        self.assertGreater(score_poi(beach, {"outdoor_bias": 1.0}, ctx)["score"],
                           score_poi(beach, {}, ctx)["score"])

    def test_onboarding_spending_level_aligns_price_band(self):
        cheap = {"poi_id": "cheap", "cat": "restaurant", "type": "Nhà hàng",
                 "fee": 0, "rating": 4.5, "intensity": 1, "price_level": 1,
                 "tags": []}
        ctx = {"hour": "12:00"}
        budget_user = score_poi(cheap, {"spending_level": 1}, ctx)["score"]
        luxury_user = score_poi(cheap, {"spending_level": 3}, ctx)["score"]
        self.assertGreater(budget_user, luxury_user)


if __name__ == "__main__":
    unittest.main()
