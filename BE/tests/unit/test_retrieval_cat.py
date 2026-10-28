"""Unit test for the activity filter on canonical `cat` (lane C).

Covers: cat beats raw Vietnamese type, whole-word match, longest phrase
first, no-diacritic/NFD input, lodging/transport not activities,
unmatched activities reported, soften-once wrapper, real-snapshot coverage.

Run from repo root: python BE/tests/unit/test_retrieval_cat.py -v
"""

import os
import sys
import unicodedata
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.retrieval import (  # noqa: E402
    ACTIVITY_TYPE_MAP, NON_ACTIVITY_CATS, load_pois_json, match_activity,
    retrieve, retrieve_softened, uncertainty)

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
    def test_cat_not_raw_type(self):
        out = retrieve(dict(TRIP, activities=["tắm biển"]), POIS)
        self.assertEqual(ids(out, "candidates"), ["son-tra-beach"])
        self.assertIn("khop loai beach", out["candidates"][0]["reasons"])

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
        self.assertEqual(ids(out, "candidates"), ["cafe"])

    def test_softened_once_keeps_hard(self):
        trip = dict(TRIP, activities=["bảo tàng"], avoid=["cafe"])
        self.assertEqual(retrieve(trip, POIS)["candidates"], [])
        out = retrieve_softened(trip, POIS)
        self.assertEqual(out["softened"], ["activities (bo loc loai, giu avoid+budget)"])
        self.assertEqual(ids(out, "candidates"), ["pagoda", "son-tra-beach"])
        self.assertEqual(retrieve_softened(dict(trip, activities=["chùa"]), POIS)["softened"],
                         [])

    def test_unmatched_activity_never_softened(self):
        trip = dict(TRIP, activities=["đi chơi"], avoid=["son-tra-beach"],
                    start_time="23:00", end_time="23:30")
        out = retrieve_softened(trip, POIS)
        self.assertEqual(out["candidates"], [])
        self.assertEqual(out["softened"], [])
        self.assertEqual(out["unmatched_activities"], ["đi chơi"])

    def test_paid_group_price_label(self):
        self.assertIn("gia chua xac minh", uncertainty(POIS[1]))
        self.assertNotIn("gia chua xac minh", uncertainty(POIS[0]))

    def test_every_snapshot_group_reachable(self):
        cats = {p.get("cat") for p in load_pois_json(SNAPSHOT)} - NON_ACTIVITY_CATS
        reachable = {c for groups in ACTIVITY_TYPE_MAP.values() for c in groups}
        self.assertEqual(cats - reachable, set())


if __name__ == "__main__":
    unittest.main()
