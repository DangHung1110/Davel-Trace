"""The independent plan audit (BE/tools/audit_plans.py) flags what it says it flags.

Its rules are written apart from the app's gate on purpose, so they need their own
pins: a number in docs/plan-accuracy.md is only as good as the check that counted it.

Run: python -m pytest BE/tests/unit/test_audit_plans.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.tools import audit_plans  # noqa: E402

TRIP = {"start_time": "08:00", "end_time": "20:00", "budget": 3_000_000, "travelers": 2}
POIS = {
    "park": {"poi_id": "park", "name": "Park", "cat": "park", "verified": True, "rating": 4.5,
             "review_count": 500, "opening_hours": ["00:00-23:59"]},
    "museum": {"poi_id": "museum", "name": "Museum", "cat": "museum", "verified": True, "rating": 4.4,
               "review_count": 900, "opening_hours": ["08:00-17:00"]},
    "lunch": {"poi_id": "lunch", "name": "Lunch", "cat": "restaurant", "verified": True, "rating": 4.6,
              "review_count": 2000, "opening_hours": ["10:00-22:00"]},
    "dinner": {"poi_id": "dinner", "name": "Dinner", "cat": "restaurant", "verified": True, "rating": 4.6,
               "review_count": 2000, "opening_hours": ["10:00-22:00"]},
    "cafe": {"poi_id": "cafe", "name": "Cafe", "cat": "cafe", "verified": True, "rating": 4.7,
             "review_count": 800, "opening_hours": ["07:00-22:00"]},
    "hill": {"poi_id": "hill", "name": "Hill park", "cat": "attraction", "verified": True, "rating": 4.5,
             "review_count": 70000, "opening_hours": ["08:00-22:00"]},
}
CELLS = {f"{a}->{b}": {"minutes": 10, "km": 3.0} for a in POIS for b in POIS if a != b}
GOOD_DAY = [("park", "08:00", "09:00"), ("museum", "09:20", "10:40"), ("lunch", "11:00", "12:00"),
            ("cafe", "13:00", "14:30"), ("dinner", "17:45", "18:45")]


def day(*stops):
    return [{"poi_id": pid, "start": start, "end": end} for pid, start, end in stops]


def kinds(stops, rest=45, trip=TRIP):
    flags, _stats = audit_plans.audit_day(day(*stops), trip, POIS, CELLS, "", set(), rest)
    return sorted({flag.split()[0] for flag in flags})


class TestAuditDay(unittest.TestCase):
    def test_a_hole_before_dinner_is_the_only_flag_of_this_day(self):
        self.assertEqual(kinds(GOOD_DAY), ["Q_HOLE"])                # 14:30 -> 17:45

    def test_a_full_day_is_clean(self):
        stops = [("hill", "08:00", "09:00"), ("museum", "09:20", "10:40"), ("lunch", "11:00", "12:00"),
                 ("cafe", "13:00", "15:00"), ("park", "15:20", "16:50"), ("dinner", "17:45", "18:45")]
        self.assertEqual(kinds(stops), [])

    def test_a_late_start_and_a_missing_dinner_are_counted(self):
        stops = [("lunch", "11:00", "12:00"), ("cafe", "13:00", "14:00"), ("museum", "14:20", "15:20"),
                 ("park", "15:40", "16:40")]
        self.assertEqual(kinds(stops), ["Q_EARLY_END", "Q_LATE_START", "Q_NO_DINNER"])

    def test_what_cannot_be_followed_is_an_error(self):
        closed = kinds([("museum", "17:30", "18:30")], trip={**TRIP, "end_time": "19:00"})
        self.assertIn("ERR_HOURS", closed)
        rushed = kinds([("park", "08:00", "09:00"), ("museum", "09:05", "10:05")])
        self.assertIn("ERR_TRAVEL", rushed)                           # 5 minutes for a 10-minute leg
        overlap = kinds([("park", "08:00", "09:00"), ("museum", "08:30", "09:30")])
        self.assertIn("ERR_OVERLAP", overlap)

    def test_an_all_day_place_through_lunch_is_not_a_missing_lunch(self):
        stops = [("hill", "08:00", "15:00"), ("cafe", "16:00", "17:00"), ("dinner", "17:45", "18:45")]
        self.assertNotIn("Q_NO_LUNCH", kinds(stops))
        self.assertIn("Q_NO_LUNCH", kinds([("park", "08:00", "09:00"), ("cafe", "09:20", "10:20"),
                                           ("museum", "13:30", "14:30"), ("dinner", "17:45", "18:45")]))


class TestShortestPath(unittest.TestCase):
    def test_best_path_is_the_shortest_open_path(self):
        place = {"a": 0, "b": 1, "c": 2}
        cells = {f"{x}->{y}": {"minutes": 10 * abs(place[x] - place[y])} for x in place for y in place if x != y}
        self.assertEqual(audit_plans.best_path(["b", "a", "c"], cells), 20)
        self.assertEqual(audit_plans.best_path(["a"], cells), 0)


if __name__ == "__main__":
    unittest.main()
