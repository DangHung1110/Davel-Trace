"""What an app replan plans: the rest of the trip from now (planning_lifecycle).

Three leaks closed here, all on POST /v1/trips/{id}/replans:
- the time: the app sends no `remaining_from`, so a replan at 14:00 started the day
  at `day_start` again; now the server's clock (Asia/Ho_Chi_Minh) is the default;
- the day: the planner always got `start_date` and every day, so a replan on day 2
  planned day 1 again; now only the days left are planned, and when the first of them
  is already under way it resumes (`TripRequest.resume`) while the next starts as usual;
- the constraints: the app sends no `changed_constraints`, so must_visit, avoid,
  areas and the budget confirmed for the source version were lost; now they are reused.

Run: python -m pytest BE/tests/unit/test_replan_window.py -q
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime, time, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.modules.identity.service import IdentityError  # noqa: E402
from BE.app.modules.planning_lifecycle.api import ConstraintOverrides  # noqa: E402
from BE.app.modules.planning_lifecycle.service import (  # noqa: E402
    MIN_DAY_LEFT_MIN,
    _current_stop,
    _moment,
    _replan_overrides,
    _trip_request,
    _window,
)
from BE.app.schemas.trip import TripRequest  # noqa: E402
from BE.app.services import gate, multiday  # noqa: E402

VN = timezone(timedelta(hours=7))

TWO_DAYS = {
    "id": "t2", "start_date": "2026-11-24", "end_date": "2026-11-25",
    "day_start": "08:00:00", "day_end": "20:00:00",
    "days": [{"date": "2026-11-24", "position": 0}, {"date": "2026-11-25", "position": 1}],
    "traveler_count": 2, "indicative_budget": 2000000, "preferred_transport": "motorbike",
    "profile_snapshot": {}, "preference_overrides": {},
}
ONE_DAY = {**TWO_DAYS, "id": "t1", "end_date": "2026-11-24", "days": TWO_DAYS["days"][:1]}


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """A moment of November 2026 on Đà Nẵng's clock."""
    return datetime(2026, 11, day, hour, minute, tzinfo=VN)


class TestMoment(unittest.TestCase):
    def test_nothing_sent(self):
        self.assertEqual(_moment(None), (None, None))
        self.assertEqual(_moment("  "), (None, None))

    def test_a_time_of_day(self):
        self.assertEqual(_moment("14:05"), (None, time(14, 5)))
        self.assertEqual(_moment("14:05:30"), (None, time(14, 5, 30)))

    def test_a_local_moment_names_its_day(self):
        self.assertEqual(_moment("2026-11-24T14:05:00"), (date(2026, 11, 24), time(14, 5)))
        self.assertEqual(_moment("2026-11-24 14:05"), (date(2026, 11, 24), time(14, 5)))

    def test_what_dart_sends(self):
        # DateTime.now().toIso8601String() on the phone: local, milliseconds, no offset.
        self.assertEqual(_moment("2026-11-24T14:05:00.000"), (date(2026, 11, 24), time(14, 5)))

    def test_an_offset_is_read_on_da_nang_clock(self):
        self.assertEqual(_moment("2026-11-24T07:05:00Z"), (date(2026, 11, 24), time(14, 5)))
        self.assertEqual(_moment("2026-11-24T14:05:00+07:00"), (date(2026, 11, 24), time(14, 5)))
        # Late evening in UTC is already the next morning in Đà Nẵng.
        self.assertEqual(_moment("2026-11-24T23:30:00Z"), (date(2026, 11, 25), time(6, 30)))

    def test_anything_else_is_refused(self):
        with self.assertRaises(IdentityError) as caught:
            _moment("soon")
        self.assertEqual((caught.exception.code, caught.exception.status),
                         ("VALIDATION_ERROR", 422))


class TestWindow(unittest.TestCase):
    def window(self, now=None, remaining_from=None, snapshot=TWO_DAYS):
        return _window(snapshot, remaining_from, now)

    def test_a_fresh_plan_is_the_whole_trip(self):
        self.assertEqual(self.window(), {"day": 1, "date": "2026-11-24", "days": 2,
                                         "start_time": "08:00"})

    def test_before_the_trip_the_whole_trip(self):
        self.assertEqual(self.window(at(23, 15)), self.window())

    def test_after_the_trip_the_whole_trip_as_before(self):
        self.assertEqual(self.window(at(26, 10)), self.window())

    def test_in_the_middle_of_the_first_day(self):
        self.assertEqual(self.window(at(24, 14, 5)),
                         {"day": 1, "date": "2026-11-24", "days": 2, "start_time": "14:05"})

    def test_never_before_the_day_starts(self):
        self.assertEqual(self.window(at(24, 6, 30))["start_time"], "08:00")

    def test_on_the_second_day_only_that_day(self):
        self.assertEqual(self.window(at(25, 9, 15)),
                         {"day": 2, "date": "2026-11-25", "days": 1, "start_time": "09:15"})

    def test_the_clock_is_read_in_da_nang(self):
        utc = timezone.utc
        self.assertEqual(self.window(datetime(2026, 11, 24, 7, 5, tzinfo=utc))["start_time"],
                         "14:05")
        # 17:30 UTC on the 24th is 00:30 on the 25th: day 2, from its start.
        self.assertEqual(self.window(datetime(2026, 11, 24, 17, 30, tzinfo=utc)),
                         {"day": 2, "date": "2026-11-25", "days": 1, "start_time": "08:00"})

    def test_an_evening_goes_on_to_the_next_day(self):
        self.assertEqual(self.window(at(24, 19, 30)),
                         {"day": 2, "date": "2026-11-25", "days": 1, "start_time": "08:00"})

    def test_an_hour_left_is_still_today(self):
        last = 20 * 60 - MIN_DAY_LEFT_MIN
        self.assertEqual(self.window(at(24, last // 60, last % 60))["day"], 1)
        self.assertEqual(self.window(at(24, last // 60, last % 60 + 1))["day"], 2)

    def test_after_the_last_day_nothing_is_left(self):
        for now in (at(25, 19, 30), at(25, 21)):
            with self.assertRaises(IdentityError) as caught:
                self.window(now)
            self.assertEqual((caught.exception.code, caught.exception.status),
                             ("REPLAN_WINDOW_CLOSED", 409))

    def test_the_device_time_wins_over_the_clock(self):
        self.assertEqual(self.window(at(24, 14), "2026-11-25T10:00:00+07:00"),
                         {"day": 2, "date": "2026-11-25", "days": 1, "start_time": "10:00"})

    def test_a_time_of_day_is_today_by_the_clock(self):
        self.assertEqual(self.window(at(25, 8), "15:30"),
                         {"day": 2, "date": "2026-11-25", "days": 1, "start_time": "15:30"})

    def test_a_time_of_day_without_a_clock_is_the_first_day(self):
        self.assertEqual(self.window(remaining_from="14:10"),
                         {"day": 1, "date": "2026-11-24", "days": 2, "start_time": "14:10"})

    def test_a_one_day_trip(self):
        self.assertEqual(self.window(at(24, 14, 5), snapshot=ONE_DAY),
                         {"day": 1, "date": "2026-11-24", "days": 1, "start_time": "14:05"})
        with self.assertRaises(IdentityError):
            self.window(at(24, 19, 30), snapshot=ONE_DAY)

    def test_a_trip_without_day_rows_is_one_day(self):
        snapshot = {key: value for key, value in ONE_DAY.items() if key != "days"}
        self.assertEqual(self.window(at(24, 9), snapshot=snapshot)["days"], 1)


class TestTripRequest(unittest.TestCase):
    """`_trip_request` over a window the service resolved on its clock."""

    def plan(self, snapshot=TWO_DAYS, **remaining):
        return _trip_request(snapshot, remaining)

    def test_the_second_day_alone(self):
        trip = self.plan(window=_window(TWO_DAYS, None, at(25, 9, 15)))
        self.assertEqual((trip["date"], trip["days"], trip["start_time"]),
                         ("2026-11-25", 1, "09:15"))
        self.assertIsNone(trip["resume"])

    def test_a_stop_of_yesterday_is_behind_a_night_at_the_base(self):
        trip = self.plan({**TWO_DAYS, "base_poi_id": "hotel"},
                         window=_window(TWO_DAYS, None, at(25, 9, 15)),
                         current_poi_id="dinner", current_poi_date="2026-11-24")
        self.assertEqual(trip["origin"]["poi_id"], "hotel")

    def test_a_stop_of_today_is_where_the_day_resumes(self):
        trip = self.plan({**TWO_DAYS, "base_poi_id": "hotel"},
                         window=_window(TWO_DAYS, None, at(25, 11)),
                         current_poi_id="museum", current_poi_date="2026-11-25")
        self.assertEqual(trip["origin"]["poi_id"], "museum")

    def test_the_first_day_resumes_and_the_second_starts_as_usual(self):
        trip = self.plan({**TWO_DAYS, "base_poi_id": "hotel"},
                         window=_window(TWO_DAYS, None, at(24, 14, 5)),
                         current_poi_id="cafe", current_poi_date="2026-11-24")
        self.assertEqual((trip["date"], trip["days"]), ("2026-11-24", 2))
        self.assertEqual((trip["start_time"], trip["origin"]["poi_id"]), ("08:00", "hotel"))
        self.assertEqual(trip["resume"]["start_time"], "14:05")
        self.assertEqual(trip["resume"]["origin"]["poi_id"], "cafe")

    def test_an_open_tour_resumes_later_only(self):
        trip = self.plan(window=_window(TWO_DAYS, None, at(24, 14, 5)))
        self.assertIsNone(trip["origin"])
        self.assertEqual(trip["resume"]["start_time"], "14:05")
        self.assertIsNone(trip["resume"]["origin"])

    def test_a_day_that_has_not_started_needs_no_resume(self):
        trip = self.plan({**TWO_DAYS, "base_poi_id": "hotel"},
                         window=_window(TWO_DAYS, None, at(24, 7)))
        self.assertEqual((trip["start_time"], trip["days"]), ("08:00", 2))
        self.assertIsNone(trip["resume"])

    def test_what_is_behind_is_no_longer_a_must(self):
        snapshot = {**TWO_DAYS, "must_visit": ["bana", "cafe", "museum", "beach"],
                    "avoid": ["market"]}
        trip = self.plan(snapshot, completed_poi_ids=["cafe"], skipped_poi_ids=["museum"],
                         unavailable_poi_ids=["beach"])
        self.assertEqual(trip["must_visit"], ["bana"])
        self.assertEqual(trip["avoid"], ["market", "beach", "cafe", "museum"])

    def test_what_was_spent_is_gone_from_the_budget(self):
        self.assertEqual(self.plan(actual_spend=450000)["budget"], 1550000)

    def test_without_a_window_the_old_reading_holds(self):
        # The service always resolves one; a call without it reads remaining_from alone.
        trip = self.plan(ONE_DAY, remaining_from="14:10", current_poi_id="cafe")
        self.assertEqual((trip["start_time"], trip["origin"]["poi_id"]), ("14:10", "cafe"))


class TestReplanOverrides(unittest.TestCase):
    SOURCE = {"trip": {}, "request_kind": "plan", "constraint_overrides": {
        "must_visit": ["bana"], "avoid": ["market"], "activities": ["biển"],
        "food_preferences": ["hải sản"], "areas": ["son_tra_my_khe"],
        "indicative_budget": 1500000.0, "base_poi_id": "hotel",
    }}

    def merged(self, changes):
        overrides = _replan_overrides(self.SOURCE, changes)
        return ConstraintOverrides.model_validate(overrides).model_dump(
            exclude_none=True, exclude_unset=True)

    def test_nothing_changed_keeps_what_was_confirmed(self):
        self.assertEqual(self.merged({}), self.SOURCE["constraint_overrides"])

    def test_a_change_replaces_its_key_only(self):
        merged = self.merged({"areas": ["hoi_an"], "avoid": []})
        self.assertEqual(merged["areas"], ["hoi_an"])
        self.assertEqual(merged["avoid"], [])
        self.assertEqual(merged["must_visit"], ["bana"])
        self.assertEqual(merged["base_poi_id"], "hotel")

    def test_null_drops_an_optional_override(self):
        merged = self.merged({"areas": None, "base_poi_id": None})
        self.assertNotIn("areas", merged)
        self.assertNotIn("base_poi_id", merged)
        self.assertEqual(merged["must_visit"], ["bana"])

    def test_a_source_without_overrides(self):
        self.assertEqual(_replan_overrides(None, {"areas": ["hoi_an"]}), {"areas": ["hoi_an"]})
        self.assertEqual(_replan_overrides({"trip": {}}, {}), {})


class TestCurrentStop(unittest.TestCase):
    KNOWN = {
        "a1": {"poi_id": "market", "date": "2026-11-24", "order": ("2026-11-24", 0)},
        "a2": {"poi_id": None, "date": "2026-11-24", "order": ("2026-11-24", 1)},
        "b1": {"poi_id": "beach", "date": "2026-11-25", "order": ("2026-11-25", 0)},
    }

    def test_it_says_which_day_it_was(self):
        self.assertEqual(_current_stop(["a1", "a2"], self.KNOWN),
                         {"poi_id": "market", "date": "2026-11-24"})
        self.assertEqual(_current_stop(["b1", "a1"], self.KNOWN),
                         {"poi_id": "beach", "date": "2026-11-25"})


class TestResumeContract(unittest.TestCase):
    def test_a_one_day_trip_simply_starts_there(self):
        trip = TripRequest(days=1, start_time="08:00", origin={"poi_id": "hotel"},
                           resume={"start_time": "14:05", "origin": {"poi_id": "cafe"}})
        self.assertEqual((trip.start_time, trip.origin.poi_id, trip.resume),
                         ("14:05", "cafe", None))

    def test_without_a_place_the_trip_origin_stays(self):
        trip = TripRequest(days=1, origin={"poi_id": "hotel"}, resume={"start_time": "14:05"})
        self.assertEqual((trip.start_time, trip.origin.poi_id), ("14:05", "hotel"))

    def test_a_longer_trip_keeps_it_for_its_first_day(self):
        trip = TripRequest(days=2, start_time="08:00", resume={"start_time": "14:05"})
        self.assertEqual((trip.start_time, trip.resume.start_time), ("08:00", "14:05"))

    def test_no_resume_by_default(self):
        self.assertIsNone(TripRequest().resume)


class TestMultidayResume(unittest.TestCase):
    def test_only_the_first_day_resumes(self):
        seen = []

        def solve(day_trip, used, diagnose):
            seen.append(day_trip)
            pid = f"p{len(seen)}"
            return {"activities": [{"poi_id": pid, "start": "15:00", "end": "16:00"}],
                    "passed": True, "total_cost": 0, "activity_match": [],
                    "_context": {"trip": day_trip, "pois": [], "travel": {}}}

        trip = {"days": 2, "date": "2026-11-24", "start_time": "08:00", "origin_id": "hotel",
                "budget": None, "resume": {"start_time": "14:05", "origin_id": "cafe"}}
        multiday.build_trip(solve, trip, lambda itinerary, whole: {
            "passed": True, "failed": [], "soft_failed": [], "checks": {}})
        first, second = seen
        self.assertEqual((first["start_time"], first["origin_id"]), ("14:05", "cafe"))
        self.assertEqual((second["start_time"], second["origin_id"]), ("08:00", "hotel"))
        self.assertNotIn("resume", first)
        self.assertNotIn("resume", second)

    def test_an_open_first_day(self):
        seen = []

        def solve(day_trip, used, diagnose):
            seen.append(day_trip)
            return {"activities": [{"poi_id": f"p{len(seen)}", "start": "15:00", "end": "16:00"}],
                    "passed": True, "total_cost": 0, "activity_match": [],
                    "_context": {"trip": day_trip, "pois": [], "travel": {}}}

        trip = {"days": 2, "date": "", "start_time": "08:00", "origin_id": "hotel",
                "budget": None, "resume": {"start_time": "14:05", "origin_id": None}}
        multiday.build_trip(solve, trip, lambda itinerary, whole: {
            "passed": True, "failed": [], "soft_failed": [], "checks": {}})
        self.assertIsNone(seen[0]["origin_id"])
        self.assertEqual(seen[1]["origin_id"], "hotel")


class TestGateFirstDay(unittest.TestCase):
    TRIP = {"days": 2, "start_time": "08:00", "end_time": "20:00", "origin_id": "hotel",
            "profile": {"pace": 2},
            "resume": {"start_time": "14:30", "origin_id": "cafe"}}
    DAY_1 = {"activities": [{"poi_id": "museum", "start": "14:40", "end": "16:00", "day": 1}]}

    def test_the_first_day_has_its_own_clock_and_place(self):
        judged = gate.day_trip(self.DAY_1, self.TRIP)
        self.assertEqual((judged["start_time"], judged["origin_id"]), ("14:30", "cafe"))
        self.assertNotIn("resume", judged)

    def test_the_other_days_keep_the_trip(self):
        day_2 = {"activities": [{"poi_id": "beach", "start": "08:30", "end": "10:00", "day": 2}]}
        self.assertIs(gate.day_trip(day_2, self.TRIP), self.TRIP)

    def test_a_trip_without_resume_is_unchanged(self):
        trip = {key: value for key, value in self.TRIP.items() if key != "resume"}
        self.assertIs(gate.day_trip(self.DAY_1, trip), trip)

    def test_an_afternoon_first_day_owes_no_lunch(self):
        pois = {"museum": {"poi_id": "museum", "category": "museum"}}
        trip = {key: value for key, value in self.TRIP.items() if key != "resume"}
        self.assertFalse(gate.check_rest_follows_lunch(self.DAY_1, trip, pois, {})["passed"])
        self.assertTrue(gate.check_rest_follows_lunch(self.DAY_1, self.TRIP, pois, {})["passed"])

    def test_the_first_drive_is_from_where_the_traveller_is(self):
        matrix = {"hotel->museum": {"minutes": 5}, "cafe->museum": {"minutes": 20}}
        trip = {key: value for key, value in self.TRIP.items() if key != "resume"}
        self.assertTrue(gate.check_b3(self.DAY_1, trip, {}, matrix)["passed"])
        # 14:30 + 20 minutes from the cafe is after the 14:40 start.
        self.assertFalse(gate.check_b3(self.DAY_1, self.TRIP, {}, matrix)["passed"])


if __name__ == "__main__":
    unittest.main()
