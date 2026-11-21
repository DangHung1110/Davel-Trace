"""OSM name matching must not pair places on a shared city word or prefix."""

import json
import os
import sys
import unittest
from collections import Counter

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

import v2_rules as R  # noqa: E402
from migrate_v2 import osm_name_ok  # noqa: E402


class TestNameKey(unittest.TestCase):
    def test_city_words_removed(self):
        self.assertEqual(R.name_key("La Bonne Café Đà Nẵng"), "la bonne cafe")
        self.assertEqual(R.name_key("Lang Bich hoa Da Nang"), "lang bich hoa")
        self.assertEqual(R.name_key("Phố cổ Hội An"), "pho co")

    def test_shared_city_suffix_is_not_a_match(self):
        self.assertFalse(osm_name_ok({"name": "La Bonne Café Đà Nẵng"},
                                     {"name": "Lang Bich hoa Da Nang", "dist_m": 50}))
        self.assertFalse(osm_name_ok({"name": "Babylon Spa - Massage Da Nang"},
                                     {"name": "Maison Spa Da Nang", "dist_m": 50}))

    def test_real_matches_still_pass(self):
        self.assertTrue(osm_name_ok({"name": "Mộc quán Seafood Đà Nẵng"}, {"name": "Mộc Quán", "dist_m": 12}))
        self.assertTrue(osm_name_ok({"name": "MAAZI"}, {"name": "Maazi", "dist_m": 1}))


class TestSnapshotLinks(unittest.TestCase):
    def test_one_osm_element_per_active_poi(self):
        with open(os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2", "pois.json"), encoding="utf-8") as f:
            pois = [p for p in json.load(f)["pois"] if p["status"] == "active"]
        shared = {k: v for k, v in Counter(p["ext_ids"].get("osm") for p in pois
                                           if p["ext_ids"].get("osm")).items() if v > 1}
        self.assertEqual(shared, {})


if __name__ == "__main__":
    unittest.main()
