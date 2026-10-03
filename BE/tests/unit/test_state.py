"""Unit test for state store + preservation (T045). Completed immutable.

Run from repo root: python BE/tests/unit/test_state.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import state as store  # noqa: E402

ACTS = [{"poi_id": "hill", "start": "07:30", "end": "09:30"},
        {"poi_id": "beach", "start": "10:00", "end": "12:00"},
        {"poi_id": "noodle", "start": "12:30", "end": "13:30"}]


class TestState(unittest.TestCase):
    def setUp(self):
        self.s = store.new_state("t1", ACTS, "07:00", "hotel")

    def test_complete_moves(self):
        s = store.complete(self.s, "hill", "09:30")
        self.assertEqual([a["poi_id"] for a in s["completed"]], ["hill"])
        self.assertNotIn("hill", [a["poi_id"] for a in s["remaining"]])
        self.assertEqual(s["version"], 1)

    def test_delta_changes_remaining_keeps_completed(self):
        s = store.complete(self.s, "hill", "09:30")
        s2 = store.apply_delta(s, {"drop": ["noodle"],
                                   "add": [{"poi_id": "museum"}],
                                   "preferences": {"pace": "nhẹ"}})
        self.assertEqual([a["poi_id"] for a in s2["completed"]], ["hill"])
        self.assertEqual(sorted(a["poi_id"] for a in s2["remaining"]),
                         ["beach", "museum"])
        self.assertIn("noodle", [a["poi_id"] for a in s2["cancelled"]])
        self.assertEqual(s2["version"], 2)

    def test_completed_never_modified_or_deleted(self):
        s = store.complete(self.s, "hill", "09:30")
        before = [dict(a) for a in s["completed"]]
        s2 = store.apply_delta(s, {"drop": ["hill", "beach"]})
        self.assertEqual(s2["completed"], before)
        self.assertEqual(s2["history"][-1]["delta"]["ignored_completed"], ["hill"])
        self.assertNotIn("beach", [a["poi_id"] for a in s2["remaining"]])

    def test_version_bumps_each_delta(self):
        s2 = store.apply_delta(self.s, {"drop": []})
        s3 = store.apply_delta(s2, {"drop": []})
        self.assertEqual((self.s["version"], s2["version"], s3["version"]), (1, 2, 3))
        self.assertEqual(len(s3["history"]), 2)

    def test_load_unknown_raises(self):
        with self.assertRaises(KeyError):
            store.load("nope")


if __name__ == "__main__":
    unittest.main()
