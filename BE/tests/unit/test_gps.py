"""Unit test for mock GPS feed (T047). Order, monotonic, trigger.

Run from repo root: python BE/tests/unit/test_gps.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.gps import GpsFeed, load_timeline  # noqa: E402

TIMELINE = os.path.join("data", "gps", "demo_day.json")


class TestGps(unittest.TestCase):
    def test_load_order_monotonic(self):
        pts = load_timeline(TIMELINE)
        self.assertGreaterEqual(len(pts), 5)
        ats = [p["at"] for p in pts]
        self.assertEqual(ats, sorted(ats))
        self.assertEqual(len(set(ats)), len(ats))
        for p in pts:
            self.assertTrue(-90 <= p["lat"] <= 90)
            self.assertTrue(-180 <= p["lon"] <= 180)

    def test_replay_in_order_exhausts(self):
        feed = GpsFeed(load_timeline(TIMELINE))
        seen = []
        while not feed.done:
            seen.append(feed.next())
        self.assertIsNone(feed.next())
        self.assertEqual([p["at"] for p in seen],
                         sorted(p["at"] for p in seen))
        print(f"\n replayed {len(seen)} points")

    def test_trigger_point_identifiable(self):
        feed = GpsFeed(load_timeline(TIMELINE))
        triggers = feed.triggers()
        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["trigger"]["event"], "rain")
        self.assertEqual(triggers[0]["at"], "13:30")

    def test_bad_timeline_rejected(self):
        import json
        import tempfile
        bad = os.path.join(tempfile.mkdtemp(prefix="gps_"), "bad.json")
        with open(bad, "w", encoding="utf-8") as f:
            json.dump([{"at": "09:00", "lat": 16.0, "lon": 108.0},
                       {"at": "08:00", "lat": 16.0, "lon": 108.0}], f)
        with self.assertRaises(AssertionError):
            load_timeline(bad)


if __name__ == "__main__":
    unittest.main()
