"""Unit test: deterministic field normalisation (Phase 4, group A).

Covers: fee takes the web-verified ticket, price_level follows the price
band (null when unknown), "suy luận" hours are labelled inferred and dropped
on a business, same-day web/OSM sessions join into one element, rule
durations read the reviewed `cat` (and landmark name prefixes) while human
durations stay, every rule is idempotent, the committed snapshot is already
normalised, the measured safe-hours table matches the snapshot, a POI
without hours takes its group's safe window, and the planner treats a null
price level as the middle band.

Run from repo root: python BE/tests/unit/test_normalize_fields.py -v
"""

import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.common import (  # noqa: E402
    SAFE_HOURS, UNKNOWN_PRICE_LEVEL, poi_open_windows, price_level_of, to_min)
from BE.app.services.rank import score_poi  # noqa: E402
from BE.app.services.retrieval import uncertainty  # noqa: E402
from BE.ml.data.normalize_fields import normalize, safe_hours  # noqa: E402
from BE.ml.patm.estimate_duration import duration_category  # noqa: E402

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "snapshots",
                        "danang-v1", "pois.json")


def poi(**kw):
    base = {"poi_id": "x", "name": "X", "type": "Nhà hàng", "cat": "restaurant",
            "verified": True, "fee": 0, "price_level": 2, "rating": 4.0,
            "tags": [], "opening_hours": ["08:00-22:00"],
            "visit_min": {"p25": 42, "p50": 60, "p75": 84},
            "dur_source": "category_rule", "smart_tags": {"price_band": "medium"}}
    base.update(kw)
    return base


def run(p):
    pois = [p]
    normalize(pois)
    return pois[0]


class TestRules(unittest.TestCase):
    def test_fee_takes_ticket(self):
        self.assertEqual(run(poi(cat="museum", ticket_vnd=60000))["fee"], 60000)
        self.assertEqual(run(poi(ticket_vnd=None))["fee"], 0)

    def test_price_level_follows_band(self):
        self.assertEqual(run(poi(smart_tags={"price_band": "cheap"}))["price_level"], 1)
        self.assertEqual(run(poi(price_level=3, smart_tags={"price_band": "medium"}))
                         ["price_level"], 2)
        self.assertIsNone(run(poi(smart_tags={"price_band": None}))["price_level"])

    def test_inferred_hours_labelled_or_dropped(self):
        guess = {"hours_web": "suy luận: bãi công cộng mở tự do"}
        beach = run(poi(cat="beach", opening_hours=["00:00-23:59"], hours_source="web",
                        web_evidence=guess))
        self.assertEqual((beach["opening_hours"], beach["hours_source"]),
                         (["00:00-23:59"], "inferred"))
        shop = run(poi(opening_hours=["00:00-23:59"], hours_source="web",
                       web_evidence=guess))
        self.assertEqual((shop["opening_hours"], shop["hours_source"]),
                         ([], "inferred_dropped"))
        sourced = run(poi(opening_hours=["07:00-17:00"], hours_source="web",
                          web_evidence={"hours_web": "07:00-17:00"}))
        self.assertEqual(sourced["hours_source"], "web")

    def test_same_day_sessions_join(self):
        p = run(poi(opening_hours=["08:00-11:30", "13:30-16:30"], hours_source="web"))
        self.assertEqual(p["opening_hours"], ["08:00-11:30, 13:30-16:30"])
        crawl = run(poi(opening_hours=["09:00-22:00", "09:30-22:00"]))
        self.assertEqual(crawl["opening_hours"], ["09:00-22:00", "09:30-22:00"])
        overlap = run(poi(opening_hours=["08:00-18:00", "09:00-12:00"], hours_source="osm"))
        self.assertEqual(overlap["opening_hours"], ["08:00-18:00", "09:00-12:00"])

    def test_duration_reads_cat_and_keeps_human(self):
        museum = run(poi(type="Điểm thu hút khách du lịch", cat="museum", rating=4.2,
                         visit_min={"p25": 140, "p50": 200, "p75": 280}))
        self.assertEqual(museum["visit_min"], {"p25": 63, "p50": 90, "p75": 126})
        human = run(poi(cat="museum", dur_source="human",
                        visit_min={"p25": 150, "p50": 210, "p75": 300}))
        self.assertEqual(human["visit_min"]["p50"], 210)

    def test_landmark_name_prefixes(self):
        self.assertEqual(duration_category({"cat": "attraction", "name": "Cầu Trần Thị Lý"}),
                         "landmark")
        self.assertEqual(duration_category({"cat": "attraction", "name": "Đỉnh Bàn Cờ"}),
                         "attraction")
        self.assertEqual(duration_category({"cat": "viewpoint", "name": "View",
                                            "type": "Điểm thu hút khách du lịch"}), "viewpoint")
        self.assertEqual(duration_category({"name": "Mới crawl", "type": "Điểm ngắm cảnh"}),
                         "Điểm ngắm cảnh")

    def test_idempotent(self):
        pois = [poi(cat="museum", ticket_vnd=50000, smart_tags={"price_band": "cheap"},
                    type="Điểm thu hút khách du lịch")]
        normalize(pois)
        again = copy.deepcopy(pois)
        report = normalize(again)
        self.assertEqual(again, pois)
        self.assertEqual(sum(report["all"].values()), 0)


class TestSnapshotNormalised(unittest.TestCase):
    def test_committed_snapshot_has_nothing_left_to_normalise(self):
        with open(SNAPSHOT, encoding="utf-8") as f:
            pois = json.load(f)["pois"]
        report = normalize(pois)
        self.assertEqual(dict(report["all"]), {})

    def test_safe_hours_table_matches_the_snapshot(self):
        with open(SNAPSHOT, encoding="utf-8") as f:
            pois = json.load(f)["pois"]
        self.assertEqual(safe_hours(pois), SAFE_HOURS)


class TestSafeHours(unittest.TestCase):
    def test_missing_hours_take_the_group_window(self):
        pagoda = {"cat": "landmark", "opening_hours": []}
        self.assertEqual(poi_open_windows(pagoda), [(to_min("08:30"), to_min("17:00"))])
        self.assertEqual(poi_open_windows({"cat": "market"}), [])
        self.assertIsNone(poi_open_windows({"cat": "lodging"}))
        self.assertIsNone(poi_open_windows({"poi_id": "fixture"}))
        real = {"cat": "landmark", "opening_hours": ["06:00-18:00"]}
        self.assertEqual(poi_open_windows(real), [(to_min("06:00"), to_min("18:00"))])


class TestPlannerUnknownPrice(unittest.TestCase):
    def test_null_price_level_is_the_middle_band(self):
        self.assertEqual(price_level_of({"price_level": None}), UNKNOWN_PRICE_LEVEL)
        self.assertEqual(price_level_of({}), UNKNOWN_PRICE_LEVEL)
        self.assertEqual(price_level_of({"price_level": 1}), 1)

    def test_rank_scores_unknown_like_the_old_placeholder(self):
        user = {"spending_level": 1, "budget": 2000000}
        unknown = score_poi(poi(price_level=None), user)
        placeholder = score_poi(poi(price_level=2), user)
        self.assertEqual(unknown["score"], placeholder["score"])

    def test_uncertainty_labels_unknown_spend(self):
        self.assertIn("gia chua xac minh", uncertainty(poi(price_level=None)))
        self.assertNotIn("gia chua xac minh", uncertainty(poi(price_level=2)))
        ticket = poi(cat="museum", smart_tags={"ticket": True}, fee=0)
        self.assertIn("gia chua xac minh", uncertainty(ticket))
        self.assertNotIn("gia chua xac minh",
                         uncertainty(poi(cat="museum", smart_tags={"ticket": True}, fee=60000)))


if __name__ == "__main__":
    unittest.main()
