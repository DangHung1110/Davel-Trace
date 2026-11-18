"""WP3: the optimizer honours EVERY opening window, not only the first.

DATA_FIX_PLAN.md WP3 acceptance: a restaurant open "11:00-14:00, 17:00-22:00"
is scheduled at dinner in a 16:00-21:00 trip (the old first-span reader only
knew 11:00-14:00, so it could never be placed).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.optimizer import StubTrip, optimize, poi_to_stub  # noqa: E402
from BE.common import parse_windows, to_min  # noqa: E402

QUAN = {"poi_id": "quan", "name": "Quán trưa-tối", "cat": "restaurant",
        "opening_hours": ["11:00-14:00, 17:00-22:00"], "visit_min": {"p25": 40, "p50": 60, "p75": 80}}
BAR = {"poi_id": "bar", "name": "Bar", "cat": "bar",
       "opening_hours": ["17:00-02:00"], "visit_min": {"p25": 45, "p50": 60, "p75": 90}}


def solve(poi, start, end):
    stub = poi_to_stub(poi)
    out = optimize([stub], {}, StubTrip(to_min(start), to_min(end), None),
                   must_visit=[poi["poi_id"]], overhead_min=0, timeout_s=10, workers=1)
    acts = (out.get("itinerary") or {}).get("activities") or []
    return out["status"], acts


class TestParseWindows(unittest.TestCase):
    def test_all_windows_and_midnight_wrap(self):
        self.assertEqual(parse_windows(["11:00-14:00, 17:00-22:00"]),
                         [(660, 840), (1020, 1320)])
        self.assertEqual(parse_windows(["17:00-02:00"]), [(1020, 1440)])
        self.assertEqual(parse_windows(["00:00-23:59"]), [(0, 1440)])
        self.assertEqual(parse_windows([]), [])


class TestMultiWindow(unittest.TestCase):
    def test_restaurant_scheduled_in_dinner_window(self):
        status, acts = solve(QUAN, "16:00", "21:00")
        self.assertIn(status, ("optimal", "feasible"))
        start = to_min(acts[0]["start"])
        self.assertGreaterEqual(start, to_min("17:00"))      # not in the 14:00-17:00 gap
        self.assertLessEqual(start + 60, to_min("21:00"))

    def test_never_placed_in_the_closed_gap(self):
        status, _acts = solve(QUAN, "14:30", "16:30")
        self.assertNotIn(status, ("optimal", "feasible"))

    def test_bar_open_past_midnight_is_schedulable_in_the_evening(self):
        status, acts = solve(BAR, "18:00", "22:00")
        self.assertIn(status, ("optimal", "feasible"))
        self.assertGreaterEqual(to_min(acts[0]["start"]), to_min("18:00"))


if __name__ == "__main__":
    unittest.main()
