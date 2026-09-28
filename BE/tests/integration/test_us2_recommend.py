"""US2 integration (T025, lane C — closes US2). Context-aware recommend.

"quán yên tĩnh hẹn hò gần biển" via retrieval (T015+T024) +
context_score (T023): matching POIs (food/space/budget) with reasons;
unverified aside; empty strict query -> soften SOFT prefs once, report
what softened, NEVER drop hard constraints (avoid/budget).

Run: python BE/tests/integration/test_us2_recommend.py -v (or pytest)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.context_score import score_context  # noqa: E402
from BE.app.services.retrieval import retrieve  # noqa: E402

POIS = [
    {"poi_id": "cove-eat", "type": "restaurant", "fee": 200000, "rating": 4.6,
     "intensity": 1, "ambience": "yên tĩnh", "crowd": "vừa phải",
     "verified": True, "opening_hours": ["10:00-22:00"],
     "tags": ["biển", "hẹn hò", "hải sản"], "cuisine": ["hải sản"]},
    {"poi_id": "club", "type": "landmark", "fee": 100000, "rating": 3.5,
     "intensity": 3, "ambience": "ồn ào", "crowd": "đông",
     "verified": True, "opening_hours": ["00:00-23:59"], "tags": ["nhạc"]},
    {"poi_id": "shack", "type": "restaurant", "fee": 50000, "rating": None,
     "intensity": 1, "ambience": "yên tĩnh", "crowd": "",
     "verified": False, "opening_hours": [], "tags": []},
    {"poi_id": "fancy", "type": "restaurant", "fee": 9000000, "rating": 4.9,
     "intensity": 1, "ambience": "lãng mạn", "crowd": "vắng",
     "verified": True, "opening_hours": ["10:00-22:00"], "tags": ["biển"]},
]
PREFS = ["yên tĩnh", "hẹn hò", "gần biển"]
TRIP = {"budget": 3000000, "start_time": "18:00", "end_time": "22:00",
        "must_visit": [], "avoid": [], "activities": ["ăn", "biển"],
        "food_prefs": ["hải sản"]}


def recommend(trip: dict, pois: list[dict], prefs: list[str]) -> dict:
    """Retrieve -> context-score; soften type prefs once if empty.

    Returns {"top": {...}|None, "ranked": [...], "softened": [...],
             "needs_verification": [...]}. Hard (avoid/budget) never dropped.
    """
    out = retrieve(trip, pois)
    softened: list[str] = []
    if not out["candidates"] and trip.get("activities"):
        trip = dict(trip, activities=[])
        softened.append("activities (bo loc loai, giu avoid+budget)")
        out = retrieve(trip, pois)
    scored = sorted(
        ({"poi_id": c["poi_id"],
          **score_context(next(p for p in pois if p["poi_id"] == c["poi_id"]),
                          prefs),
          "reasons": c["reasons"], "uncertainty": c["uncertainty"]}
         for c in out["candidates"]),
        key=lambda r: r["score"], reverse=True)
    return {"top": scored[0] if scored else None, "ranked": scored,
            "softened": softened,
            "needs_verification": out["needs_verification"]}


class TestUS2Recommend(unittest.TestCase):
    def test_matching_poi_top_with_reasons(self):
        rec = recommend(TRIP, POIS, PREFS)
        self.assertIsNotNone(rec["top"])
        self.assertEqual(rec["top"]["poi_id"], "cove-eat")
        self.assertEqual([f["rule"] for f in rec["top"]["fired"]],
                         ["quiet", "dating", "near_sea"])
        self.assertTrue(rec["top"]["reasons"])
        self.assertEqual(rec["softened"], [])

    def test_opposite_and_overbudget_aside(self):
        trip = dict(TRIP, activities=[])  # no type filter: cove + club rank
        rec = recommend(trip, POIS, PREFS)
        self.assertEqual(rec["top"]["poi_id"], "cove-eat")
        self.assertLess(rec["ranked"][-1]["score"], rec["top"]["score"])
        ordered = [r["poi_id"] for r in rec["ranked"]]
        self.assertNotIn("fancy", ordered)  # over budget
        self.assertNotIn("fancy", ordered)  # over budget
        self.assertNotIn("shack", ordered)  # unverified -> aside
        self.assertEqual([c["poi_id"] for c in rec["needs_verification"]],
                         ["shack"])

    def test_empty_softens_soft_keeps_hard(self):
        trip = dict(TRIP, activities=["bảo tàng"], avoid=["club"])
        rec = recommend(trip, POIS, PREFS)
        self.assertIsNotNone(rec["top"])
        self.assertEqual(rec["softened"], ["activities (bo loc loai, giu avoid+budget)"])
        ordered = [r["poi_id"] for r in rec["ranked"]]
        self.assertNotIn("club", ordered)  # hard avoid kept
        print(f"\n softened: {rec['softened']} top: {rec['top']['poi_id']}")


if __name__ == "__main__":
    unittest.main()
