"""Unit test: opening hours -> optimizer windows (Phase 4, group A).

Covers: spans past midnight ("19:30-03:00", "09:00-00:00") keep a usable
same-day window, lunch + dinner service are two windows (not lunch only),
weekday variants intersect (open on every variant), the optimizer and its
greedy hint place a stop in any window, and every verified snapshot POI
gets a window that can hold a visit.

Run from repo root: python BE/tests/unit/test_opening_windows.py -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.common import open_windows, parse_hours, to_min  # noqa: E402
from BE.app.services.optimizer import (  # noqa: E402
    StubPOI, StubTrip, _hint_place, optimize, poi_to_stub, poi_windows)

H = 60
SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "snapshots",
                        "danang-v1", "pois.json")


def m(hhmm):
    return to_min(hhmm)


class TestOpenWindows(unittest.TestCase):
    def test_overnight_span_moves_close_to_next_day(self):
        self.assertEqual(open_windows(["19:30-03:00"]), [(m("19:30"), 24 * H + 3 * H)])
        self.assertEqual(open_windows(["09:00-00:00"]), [(m("09:00"), 24 * H)])
        self.assertEqual(open_windows(["00:00-23:59"]), [(0, m("23:59"))])

    def test_split_service_keeps_both_windows(self):
        self.assertEqual(open_windows(["10:30-14:00, 17:30-20:45"]),
                         [(m("10:30"), m("14:00")), (m("17:30"), m("20:45"))])

    def test_weekday_variants_intersect(self):
        # lunch is closed on some days -> only dinner is safe
        self.assertEqual(open_windows(["10:30-14:00, 17:30-20:45", "17:30-20:45"]),
                         [(m("17:30"), m("20:45"))])
        self.assertEqual(open_windows(["09:00-22:00", "09:30-22:00"]),
                         [(m("09:30"), m("22:00"))])

    def test_unset_disjoint_and_stray(self):
        self.assertIsNone(open_windows([]))
        self.assertIsNone(open_windows(None))
        self.assertIsNone(open_windows(["12:03"]))
        self.assertEqual(open_windows(["08:00-11:00", "14:00-17:00"]), [])
        self.assertEqual(parse_hours(["08:00-11:00", "14:00-17:00"]), (0, 0))
        self.assertEqual(parse_hours(["10:30-14:00, 17:30-20:45"]),
                         (m("10:30"), m("14:00")))


class TestStubWindows(unittest.TestCase):
    def test_bar_past_midnight_is_open_in_the_evening(self):
        stub = poi_to_stub({"poi_id": "bar", "cat": "bar", "visit_min": {"p50": 90},
                            "opening_hours": ["19:30-03:00"]})
        self.assertEqual((stub.open_min, stub.close_min), (m("19:30"), 27 * H))
        self.assertEqual(stub.windows, ())

    def test_split_service_stub_holds_envelope_and_windows(self):
        stub = poi_to_stub({"poi_id": "r", "cat": "restaurant", "visit_min": {"p50": 60},
                            "opening_hours": ["10:30-14:00, 17:30-20:45"]})
        self.assertEqual((stub.open_min, stub.close_min), (m("10:30"), m("20:45")))
        self.assertEqual(stub.windows, ((m("10:30"), m("14:00")), (m("17:30"), m("20:45"))))

    def test_no_hours_falls_back_to_trip_window(self):
        trip = {"start_time": "08:00", "end_time": "20:00"}
        self.assertEqual(poi_windows({"poi_id": "x"}, trip), [(m("08:00"), m("20:00"))])
        self.assertEqual(poi_windows({"poi_id": "x"}, trip, deadline=m("19:00")),
                         [(m("08:00"), m("19:00"))])


class TestOptimizerWindows(unittest.TestCase):
    def test_bar_past_midnight_is_scheduled(self):
        bar = poi_to_stub({"poi_id": "bar", "cat": "bar", "visit_min": {"p50": 90},
                           "opening_hours": ["19:30-03:00"]})
        out = optimize([bar], {("depot", "bar"): 10}, StubTrip(18 * H, 23 * H),
                       require_all=True)
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        self.assertGreaterEqual(m(out["itinerary"]["activities"][0]["start"]), m("19:30"))

    def test_dinner_window_used_after_lunch_closes(self):
        cafe = StubPOI("cafe", visit_min=60, open_min=15 * H, close_min=17 * H,
                       windows=((15 * H, 16 * H), (19 * H, 21 * H)))
        out = optimize([cafe], {("depot", "cafe"): 10}, StubTrip(16 * H + 30, 21 * H),
                       require_all=True)
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        self.assertGreaterEqual(m(out["itinerary"]["activities"][0]["start"]), 19 * H)

    def test_gap_between_windows_is_closed(self):
        cafe = StubPOI("cafe", visit_min=60, open_min=10 * H, close_min=20 * H,
                       windows=((10 * H, 12 * H), (18 * H, 20 * H)))
        out = optimize([cafe], {("depot", "cafe"): 10}, StubTrip(13 * H, 17 * H),
                       require_all=True)
        self.assertEqual(out["status"], "infeasible")

    def test_greedy_hint_takes_the_next_window(self):
        cafe = StubPOI("cafe", visit_min=60, open_min=10 * H, close_min=20 * H,
                       windows=((10 * H, 12 * H), (18 * H, 20 * H)))
        spot = _hint_place(cafe, None, 15 * H, StubTrip(8 * H, 21 * H, "depot"),
                           {("depot", "cafe"): 10}, set())
        self.assertEqual(spot, (18 * H, 10, None))


class TestSnapshotWindows(unittest.TestCase):
    def test_single_variant_hours_always_hold_a_visit(self):
        # The overnight bug made 74 verified POIs (40 bars) unschedulable.
        # Only weekday variants that share no open time may come out empty.
        with open(SNAPSHOT, encoding="utf-8") as f:
            pois = [p for p in json.load(f)["pois"]
                    if p.get("verified") and len(p.get("opening_hours") or []) == 1]
        trip = {"start_time": "07:00", "end_time": "23:30"}
        unusable = [p["name"] for p in pois
                    if not any(hi - lo >= 30 for lo, hi in poi_windows(p, trip))]
        self.assertEqual(unusable, [])


if __name__ == "__main__":
    unittest.main()
