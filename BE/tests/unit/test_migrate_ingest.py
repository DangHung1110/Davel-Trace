"""WP5/WP8/WP10 ingest: user decisions and human-verify exports -> v2.1 record."""

import copy
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

from migrate_v2 import apply_decision, apply_human_verify, price_tier  # noqa: E402

from BE.tests.unit.test_poi_view_v21 import rec  # noqa: E402


class TestPriceTier(unittest.TestCase):
    def test_v20_price_object_to_tier(self):
        self.assertEqual(price_tier({"basis": "included_in_parent"}, "outdoor_landmark"), "included")
        self.assertEqual(price_tier({"free_entry": True}, "beach"), "free")
        self.assertEqual(price_tier({"typical_vnd": 60_000}, "museum_indoor"), "cheap")
        self.assertEqual(price_tier({"ticket_vnd": 900_000}, "paid_attraction"), "expensive")
        self.assertEqual(price_tier({"legacy_band_web": "medium"}, "restaurant"), "medium")
        self.assertIsNone(price_tier({"status": "unknown"}, "paid_attraction"))
        self.assertIsNone(price_tier({"typical_vnd": 1_000_000}, "lodging"))


class TestDecisions(unittest.TestCase):
    def test_rename_keeps_raw_and_marks_user(self):
        r = rec()
        apply_decision(r, {"name": "Clover Spa", "_file": "decisions_names_x.json"})
        self.assertEqual(r["name"], "Clover Spa")
        self.assertEqual(r["name_raw"], "Bảo tàng X")
        self.assertEqual(r["provenance"]["name"]["verified_by"], "user")

    def test_status_decision(self):
        r = rec(status="review")
        apply_decision(r, {"status": "active", "_file": "decisions_x.json"})
        self.assertEqual((r["status"], r["status_reason"]), ("active", None))
        apply_decision(r, {"status": "excluded", "status_reason": "tiệm hoa", "_file": "d.json"})
        self.assertEqual((r["status"], r["status_reason"]), ("excluded", "tiệm hoa"))


class TestHumanVerify(unittest.TestCase):
    def test_human_with_url_sets_fixed_hours_and_tier(self):
        r = rec(kind="safe_window", tier=None)
        apply_human_verify(r, {"hours": "07:00-17:30", "price_tier": "cheap",
                               "evidence_url": "https://example.org/ve",
                               "checked_at": "2026-11-19", "_file": "human_verify_v2_x.json"})
        self.assertEqual(r["hours"], {**r["hours"], "open": ["07:00-17:30"], "kind": "fixed"})
        self.assertEqual(r["price"]["tier"], "cheap")
        self.assertEqual(r["provenance"]["hours"]["verified_by"], "human")
        self.assertEqual(r["provenance"]["price"]["evidence_url"], "https://example.org/ve")

    def test_without_url_is_user_and_vnd_maps_to_tier(self):
        r = rec(tier=None)
        apply_human_verify(r, {"ticket_vnd": 150_000, "_file": "human_verify_v2_x.json"})
        self.assertEqual(r["price"]["tier"], "medium")
        self.assertEqual(r["provenance"]["price"]["verified_by"], "user")

    def test_bad_hours_and_inconsistent_included_are_ignored(self):
        r = rec()
        before = copy.deepcopy(r)
        apply_human_verify(r, {"hours": "sáng thứ 2", "price_tier": "included",
                               "_file": "human_verify_v2_x.json"})
        self.assertEqual(r, before)    # no parent ticket -> 'included' is invalid


if __name__ == "__main__":
    unittest.main()
