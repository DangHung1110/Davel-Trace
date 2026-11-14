"""Unit test for activity matching on canonical `cat` (lane C).

Covers: cat beats raw Vietnamese type, whole-word match, longest phrase
first, no-diacritic/NFD input, lodging/transport not activities,
activities never exclude a POI (they become `required_any` groups),
unmatched activities reported, real-snapshot coverage.

Run from repo root: python BE/tests/unit/test_retrieval_cat.py -v
"""

import os
import sys
import unicodedata
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.retrieval import (  # noqa: E402
    ACTIVITY_TYPE_MAP, NON_ACTIVITY_CATS, activity_requirements, load_pois_json,
    match_activity, retrieve, uncertainty)

POIS = [
    {"poi_id": "son-tra-beach", "type": "Điểm thu hút khách du lịch", "cat": "beach",
     "fee": 0, "verified": True, "opening_hours": ["00:00-23:59"], "tags": ["biển"]},
    {"poi_id": "cafe", "type": "Quán cà phê", "cat": "cafe", "fee": 0, "verified": True,
     "opening_hours": ["07:00-22:00"], "tags": ["Quán cà phê"]},
    {"poi_id": "hotel", "type": "Khách sạn", "cat": "lodging", "fee": 0,
     "verified": True, "opening_hours": [], "tags": ["Khách sạn"]},
    {"poi_id": "pagoda", "type": "Chùa phật giáo", "cat": "landmark", "fee": 0,
     "verified": True, "opening_hours": ["06:00-18:00"], "tags": ["Chùa"]},
]
TRIP = {"budget": 3000000, "start_time": "07:00", "end_time": "18:00",
        "must_visit": [], "avoid": [], "activities": []}
SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "snapshots",
                        "danang-v1", "pois.json")


def ids(result, key):
    return sorted(r["poi_id"] for r in result[key])


class TestActivityText(unittest.TestCase):
    def test_whole_word_not_substring(self):
        self.assertEqual(match_activity("văn hóa"), {"museum"})
        self.assertEqual(match_activity("yêu cầu yên tĩnh"), set())

    def test_longest_phrase_first(self):
        self.assertEqual(match_activity("học nấu ăn"), {"attraction"})
        self.assertEqual(match_activity("công viên giải trí"), {"attraction"})
        self.assertEqual(match_activity("quán cà phê view biển"), {"cafe"})
        self.assertEqual(match_activity("đi ăn ở quán gần biển"),
                         {"restaurant", "cafe", "bar"})

    def test_no_diacritics_and_nfd(self):
        self.assertEqual(match_activity("tam bien"), {"beach"})
        self.assertEqual(match_activity("ca phe sang"), {"cafe"})
        self.assertEqual(match_activity(unicodedata.normalize("NFD", "tắm biển")),
                         {"beach"})

    def test_groups_missing_before(self):
        self.assertEqual(match_activity("đi cà phê"), {"cafe"})
        self.assertEqual(match_activity("massage"), {"spa"})
        self.assertEqual(match_activity("đi bar"), {"bar"})


class TestCatFilter(unittest.TestCase):
    def test_activity_never_excludes(self):
        # Regression: "tắm biển" used to drop every non-beach POI, restaurants
        # included, so a profile day had no lunch and was infeasible.
        out = retrieve(dict(TRIP, activities=["tắm biển"]), POIS)
        self.assertEqual(ids(out, "candidates"), ["cafe", "pagoda", "son-tra-beach"])
        reasons = {c["poi_id"]: c["reasons"] for c in out["candidates"]}
        self.assertIn("khop hoat dong beach", reasons["son-tra-beach"])
        self.assertIn("loai cafe", reasons["cafe"])

    def test_lodging_not_activity_unless_must_visit(self):
        out = retrieve(TRIP, POIS)
        self.assertNotIn("hotel", ids(out, "candidates"))
        self.assertIn({"poi_id": "hotel", "reason": "khong phai hoat dong"},
                      out["excluded"])
        out = retrieve(dict(TRIP, must_visit=["hotel"]), POIS)
        self.assertIn("hotel", ids(out, "candidates"))

    def test_unmatched_activities_reported(self):
        out = retrieve(dict(TRIP, activities=["đi chơi", "đi cà phê"]), POIS)
        self.assertEqual(out["unmatched_activities"], ["đi chơi"])
        self.assertEqual(ids(out, "candidates"), ["cafe", "pagoda", "son-tra-beach"])

    def test_hard_filters_still_hard(self):
        trip = dict(TRIP, activities=["bảo tàng"], avoid=["cafe"],
                    start_time="23:00", end_time="23:30")
        out = retrieve(trip, POIS)
        self.assertEqual(ids(out, "candidates"), ["son-tra-beach"])
        self.assertIn({"poi_id": "cafe", "reason": "avoid"}, out["excluded"])
        self.assertIn({"poi_id": "pagoda", "reason": "dong cua trong khung gio"},
                      out["excluded"])


class TestActivityRequirements(unittest.TestCase):
    def test_groups_only_for_categories_in_pool(self):
        groups, report = activity_requirements(
            ["tắm biển", "bảo tàng", "đi chơi", "lịch sử"], POIS)
        self.assertEqual(groups, [{"count": 1, "categories": ["beach"], "poi_ids": ["son-tra-beach"]},
                                  {"count": 1, "categories": ["landmark"], "poi_ids": ["pagoda"]}])
        self.assertEqual([(r["activity"], r["status"]) for r in report],
                         [("tắm biển", "required"), ("bảo tàng", "no_verified_poi"),
                          ("đi chơi", "not_understood"), ("lịch sử", "required")])
        self.assertEqual(report[1]["categories"], ["museum"])

    def test_duplicate_groups_collapse(self):
        groups, _ = activity_requirements(["tắm biển", "đi biển"], POIS)
        self.assertEqual(groups, [{"count": 1, "categories": ["beach"], "poi_ids": ["son-tra-beach"]}])

    def test_lodging_never_required(self):
        groups, report = activity_requirements(["khách sạn"], POIS)
        self.assertEqual(groups, [])
        self.assertEqual(report[0]["status"], "not_understood")

    def test_paid_group_price_label(self):
        self.assertIn("gia chua xac minh", uncertainty(POIS[1]))
        self.assertNotIn("gia chua xac minh", uncertainty(POIS[0]))

    def test_every_snapshot_group_reachable(self):
        cats = {p.get("cat") for p in load_pois_json(SNAPSHOT)} - NON_ACTIVITY_CATS
        reachable = {c for groups in ACTIVITY_TYPE_MAP.values() for c in groups}
        self.assertEqual(cats - reachable, set())


if __name__ == "__main__":
    unittest.main()
