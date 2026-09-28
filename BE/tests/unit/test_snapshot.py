"""Unit test for snapshot loader (T008). Runs on seed danang-v1.

Stdlib unittest so it runs without lane C's pytest layout:
  python -m unittest BE.tests.unit.test_snapshot -v
  (from repo root; BE/tests/unit has no __init__ yet -> run as script too)
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.snapshot import (  # noqa: E402
    load_matrix,
    load_snapshot,
    validate_poi,
    validate_snapshot,
    verified_pois,
)

SNAPSHOT_DIR = os.path.join("data", "snapshots", "danang-v1")


class TestSnapshotSeed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_snapshot(SNAPSHOT_DIR)

    def test_seed_has_7_pois(self):
        self.assertEqual(len(self.data["pois"]), 7)

    def test_snapshot_fetched_at_required(self):
        self.assertTrue(self.data["fetched_at"])

    def test_all_pois_valid_schema(self):
        self.assertEqual(validate_snapshot(self.data), [])

    def test_all_seed_pois_verified(self):
        self.assertEqual(len(verified_pois(self.data)), 7)

    def test_matrix_7x7_matches_ids(self):
        ids = [p["poi_id"] for p in self.data["pois"]]
        matrix = load_matrix(SNAPSHOT_DIR, ids)
        self.assertEqual(len(matrix["cells"]), 49)

    def test_missing_fetched_at_rejected(self):
        bad = copy.deepcopy(self.data["pois"][0])
        del bad["fetched_at"]
        self.assertTrue(any("fetched_at" in e for e in validate_poi(bad)))

    def test_broken_visit_min_ordering_rejected(self):
        bad = copy.deepcopy(self.data["pois"][0])
        bad["visit_min"] = {"p25": 100, "p50": 50, "p75": 30}
        self.assertTrue(any("visit_min" in e for e in validate_poi(bad)))

    def test_unverified_excluded_from_main_plan(self):
        data = copy.deepcopy(self.data)
        data["pois"][0]["verified"] = False
        self.assertEqual(validate_snapshot(data), [])  # still schema-valid
        got = verified_pois(data)
        self.assertEqual(len(got), 6)
        self.assertNotIn(data["pois"][0]["poi_id"], [p["poi_id"] for p in got])


if __name__ == "__main__":
    unittest.main()
