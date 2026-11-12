"""The order polish judges the day an order gives, not its driving alone.

`route_order.best_order` used to return the shortest tour of the stops the solver
chose. The solver's objective has no word for dead time, so of two days with the same
stops it returned either: an 08:00 day that opened with lunch at 11:00, three hours
between lunch and the next stop while the cafe sat right before that lunch, a named
pagoda at 18:42 with the morning empty. On 201 real plans the audit counted 42 such
holes and 14 late starts. Dead minutes and a misplaced named place now cost driving
minutes (`route_order.timing_cost`), and the search takes the cheapest day.

Run: python -m pytest BE/tests/unit/test_order_timing.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import route_order  # noqa: E402
from BE.app.services.optimizer import StubPOI  # noqa: E402

H = 60


def mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def stubs_of(*rows):
    return {row.poi_id: row for row in rows}


def flat_travel(stubs, minutes=5):
    return {(a, b): minutes for a in stubs for b in stubs if a != b}


LUNCH = StubPOI("lunch", visit_min=40, open_min=10 * H + 30, close_min=15 * H, restaurant=True,
                category="restaurant")
DINNER = StubPOI("dinner", visit_min=60, open_min=17 * H, close_min=22 * H, restaurant=True,
                 category="restaurant")
PARK = StubPOI("park", visit_min=45, visit_max=75, open_min=5 * H, close_min=21 * H, category="park",
               windows=((5 * H, 11 * H + 30), (14 * H + 30, 21 * H)))
MUSEUM = StubPOI("museum", visit_min=60, visit_max=90, open_min=8 * H, close_min=17 * H, category="museum")
CAFE = StubPOI("cafe", visit_min=60, visit_max=120, open_min=7 * H, close_min=22 * H, category="cafe")
CHURCH = StubPOI("church", visit_min=20, visit_max=30, open_min=5 * H, close_min=18 * H, category="temple")
BRIDGE = StubPOI("bridge", visit_min=20, visit_max=30, open_min=0, close_min=24 * H, category="landmark")


class TestTimingCost(unittest.TestCase):
    ROLES = {"a": None, "lunch": "lunch", "b": None}

    def cost(self, rows, legs, rest=None, preferred=None):
        return route_order.timing_cost(rows, legs, 8 * H, self.ROLES, rest, preferred)

    def test_a_tight_day_costs_nothing(self):
        rows = [{"poi_id": "a", "start": "08:20", "end": "09:20"},
                {"poi_id": "b", "start": "09:45", "end": "10:45"}]
        self.assertEqual(self.cost(rows, [15]), 0)

    def test_a_late_start_and_a_hole_cost_by_the_minute(self):
        rows = [{"poi_id": "a", "start": "10:00", "end": "11:00"},      # 120 late, 30 free
                {"poi_id": "b", "start": "13:15", "end": "14:15"}]      # 135 gap, 15 leg, 30 free
        self.assertEqual(self.cost(rows, [15]), route_order.TIMING_WEIGHT * (90 + 90))

    def test_the_rest_after_lunch_is_not_a_hole(self):
        rows = [{"poi_id": "lunch", "start": "11:00", "end": "12:00"},
                {"poi_id": "b", "start": "13:30", "end": "14:30"}]      # 45 rest + 45 over it
        late = route_order.TIMING_WEIGHT * (3 * H - route_order.LATE_START_FREE)
        self.assertEqual(self.cost(rows, [15], rest=45), late)
        rows[1] = {"poi_id": "b", "start": "15:00", "end": "16:00"}     # 90 more: dead
        self.assertEqual(self.cost(rows, [15], rest=45), late + route_order.TIMING_WEIGHT * 90)

    def test_a_named_place_outside_its_hours_is_misplaced(self):
        rows = [{"poi_id": "a", "start": "08:00", "end": "09:00"},
                {"poi_id": "b", "start": "09:15", "end": "10:15"}]
        self.assertEqual(self.cost(rows, [15], preferred={"b": [(5 * H, 18 * H)]}), 0)
        self.assertEqual(self.cost(rows, [15], preferred={"b": [(14 * H, 18 * H)]}),
                         route_order.MISPLACED_COST)


class TestBestOrderFillsTheDay(unittest.TestCase):
    def test_a_day_does_not_open_with_lunch_when_the_morning_can_hold_stops(self):
        # What the solver returned for an 08:00-20:00 day (audit W19, savings).
        stubs = stubs_of(LUNCH, MUSEUM, CHURCH, BRIDGE, PARK, CAFE, DINNER)
        acts = [{"poi_id": "lunch", "start": "11:00", "end": "11:40"},
                {"poi_id": "museum", "start": "12:25", "end": "13:34"},
                {"poi_id": "church", "start": "13:49", "end": "14:09"},
                {"poi_id": "bridge", "start": "14:24", "end": "14:44"},
                {"poi_id": "park", "start": "15:18", "end": "16:03"},
                {"poi_id": "cafe", "start": "16:17", "end": "17:17"},
                {"poi_id": "dinner", "start": "17:30", "end": "18:30"}]
        rows = route_order.best_order(acts, stubs, flat_travel(stubs), 8 * H, 20 * H, 12, rest_minutes=45)
        self.assertLessEqual(mins(rows[0]["start"]), 8 * H + route_order.LATE_START_FREE, rows)
        self.assertNotEqual(rows[0]["poi_id"], "lunch")
        by_id = {row["poi_id"]: row for row in rows}
        self.assertTrue(11 * H <= mins(by_id["lunch"]["start"]) < 13 * H)       # still a lunch
        self.assertTrue(17 * H + 30 <= mins(by_id["dinner"]["start"]) < 20 * H + 30)

    def test_the_cafe_fills_the_hole_after_lunch(self):
        # Audit T15 (balanced): cafe 10:43, lunch 11:59, then nothing until 16:01.
        stubs = stubs_of(BRIDGE, CHURCH, CAFE, LUNCH, PARK, DINNER)
        acts = [{"poi_id": "bridge", "start": "08:00", "end": "08:20"},
                {"poi_id": "church", "start": "09:19", "end": "09:49"},
                {"poi_id": "cafe", "start": "10:43", "end": "11:43"},
                {"poi_id": "lunch", "start": "11:59", "end": "12:39"},
                {"poi_id": "park", "start": "16:01", "end": "17:16"},
                {"poi_id": "dinner", "start": "17:30", "end": "18:30"}]
        rows = route_order.best_order(acts, stubs, flat_travel(stubs), 8 * H, 20 * H, 12, rest_minutes=60)
        order = [row["poi_id"] for row in rows]
        self.assertLess(order.index("lunch"), order.index("cafe"), rows)
        for before, after in zip(rows, rows[1:]):
            limit = 60 + route_order.REST_EXTRA_FREE + 17 if before["poi_id"] == "lunch" else 60
            self.assertLessEqual(mins(after["start"]) - mins(before["end"]), limit, rows)

    def test_driving_still_counts(self):
        # Equal days: the shorter drive wins, as before.
        stubs = stubs_of(*(StubPOI(p, visit_min=30, open_min=8 * H, close_min=20 * H, category=p)
                           for p in "abcd"))
        place = {"a": 0, "b": 1, "c": 2, "d": 3}
        travel = {(x, y): 10 * abs(place[x] - place[y]) for x in place for y in place if x != y}
        acts = [{"poi_id": p, "start": f"{8 + i * 2:02d}:00", "end": f"{8 + i * 2:02d}:30"}
                for i, p in enumerate("cadb")]
        ids = [row["poi_id"] for row in route_order.best_order(acts, stubs, travel, 8 * H, 20 * H, 5)]
        self.assertIn(ids, (list("abcd"), list("dcba")))


class TestNamedPlaceKeepsSensibleHours(unittest.TestCase):
    def test_a_named_pagoda_moves_out_of_the_dark_when_the_morning_is_free(self):
        # Audit M02 (savings): Chùa Linh Ứng at 18:42 after dinner, the morning empty.
        pagoda = StubPOI("pagoda", visit_min=50, visit_max=75, open_min=6 * H, close_min=21 * H,
                         category="temple")           # named: only its opening hours bind
        stubs = stubs_of(LUNCH, MUSEUM, CAFE, DINNER, pagoda)
        travel = flat_travel(stubs)
        acts = [{"poi_id": "lunch", "start": "11:00", "end": "11:40"},
                {"poi_id": "museum", "start": "12:25", "end": "13:55"},
                {"poi_id": "cafe", "start": "14:09", "end": "15:43"},
                {"poi_id": "dinner", "start": "17:30", "end": "18:10"},
                {"poi_id": "pagoda", "start": "18:42", "end": "19:57"}]
        rows = route_order.best_order(acts, stubs, travel, 8 * H, 20 * H, 12, rest_minutes=45,
                                      preferred={"pagoda": [(6 * H, 18 * H)]})
        visit = next(row for row in rows if row["poi_id"] == "pagoda")
        self.assertLessEqual(mins(visit["end"]), 18 * H, rows)

    def test_without_a_sensible_slot_it_stays_where_it_fits(self):
        pagoda = StubPOI("pagoda", visit_min=50, open_min=6 * H, close_min=21 * H, category="temple")
        stubs = stubs_of(DINNER, pagoda)
        acts = [{"poi_id": "dinner", "start": "18:30", "end": "19:30"},
                {"poi_id": "pagoda", "start": "19:45", "end": "20:35"}]
        rows = route_order.best_order(acts, stubs, flat_travel(stubs), 18 * H + 30, 21 * H, 12,
                                      preferred={"pagoda": [(6 * H, 18 * H)]})
        self.assertEqual({row["poi_id"] for row in rows}, {"dinner", "pagoda"})


class TestKeptDry(unittest.TestCase):
    def test_wet_hours_leave_the_windows(self):
        beach = StubPOI("beach", visit_min=90, open_min=6 * H, close_min=19 * H, category="beach")
        dry = route_order.kept_dry(beach, [(13 * H, 17 * H)])
        self.assertEqual(dry.windows, ((6 * H, 13 * H), (17 * H, 19 * H)))

    def test_a_stop_seated_in_the_dry_morning_is_not_moved_into_the_rain(self):
        beach = route_order.kept_dry(
            StubPOI("beach", visit_min=90, open_min=6 * H, close_min=19 * H, category="beach"),
            [(13 * H, 20 * H)])
        # The museum is on the way out, the beach at the far end: shortest is museum first.
        stubs = stubs_of(beach, MUSEUM, LUNCH)
        travel = {("museum", "lunch"): 5, ("lunch", "museum"): 5, ("lunch", "beach"): 5,
                  ("beach", "lunch"): 5, ("museum", "beach"): 40, ("beach", "museum"): 40}
        acts = [{"poi_id": "beach", "start": "08:00", "end": "09:30"},
                {"poi_id": "museum", "start": "10:10", "end": "11:10"},
                {"poi_id": "lunch", "start": "11:30", "end": "12:10"}]
        rows = route_order.best_order(acts, stubs, travel, 8 * H, 20 * H, 12)
        visit = next(row for row in rows if row["poi_id"] == "beach")
        self.assertLessEqual(mins(visit["end"]), 13 * H, rows)


if __name__ == "__main__":
    unittest.main()
