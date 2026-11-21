"""The forecast reaches the plan: rain moves open-air stops, and the date picks the day.

Before: the rain probability only fed the rank list, which orders candidates and
explains them. With 90 % rain all day every profile still opened at the beach or the
park, and a trip dated next Saturday was planned on today's hours of the forecast.

Now (`trip_ctx.rain_costs`, `forecast_day`):
- an hour more likely wet than dry costs an exposed stop in the solver, by how wet a
  visitor gets there (`smart_tags.rain_cover`); in near-certain rain more than the stop
  is worth, so it is left out unless a wish, a named place or the pace floor needs it;
- rain for part of the day moves the stop to the dry hours;
- a stop that stays in the open in a wet hour is named in the plan's warnings;
- the forecast is read on the trip's date, and a date it does not cover has no forecast.

Run: python -m pytest BE/tests/unit/test_rain_planning.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import trip_ctx  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, _greedy_hint, optimize  # noqa: E402
from BE.app.services.profiles import build_plan  # noqa: E402
from BE.tests.unit.test_template_wiring import BY_ID, CELLS, RANKED, _trip  # noqa: E402

H = 60
DAY = {"start_time": "08:00", "end_time": "20:00"}
PROFILE = {"party_type": "solo", "pace": 2, "fitness": 2}


def _forecast(rain, date="2026-11-14", temp=27.0):
    """24 hours of `date`; `rain` is a probability or a function of the hour."""
    at = rain if callable(rain) else (lambda hour: rain)
    return {"source": "injected", "stale": False,
            "hourly": [{"at": f"{date}T{hour:02d}:00", "temp_c": temp, "rain_prob": at(hour)}
                       for hour in range(24)]}


def _afternoon_rain(hour):
    return 0.9 if 13 <= hour <= 17 else 0.1


class TestForecastOfTheTripDate(unittest.TestCase):
    WEEK = {"source": "injected", "stale": False,
            "hourly": (_forecast(0.0, "2026-11-14")["hourly"] + _forecast(0.9, "2026-11-15")["hourly"])}

    def test_the_date_picks_its_own_day(self):
        saturday = trip_ctx.build({**DAY, "date": "2026-11-14"}, PROFILE, forecast=self.WEEK,
                                  fetch_weather=False)
        sunday = trip_ctx.build({**DAY, "date": "2026-11-15"}, PROFILE, forecast=self.WEEK,
                                fetch_weather=False)
        self.assertEqual(saturday["rain_prob"], 0.0)
        self.assertEqual(sunday["rain_prob"], 0.9)
        self.assertFalse(trip_ctx.is_wet(saturday))
        self.assertTrue(trip_ctx.is_wet(sunday))

    def test_no_date_reads_the_first_day_as_before(self):
        ctx = trip_ctx.build(DAY, PROFILE, forecast=self.WEEK, fetch_weather=False)
        self.assertEqual(ctx["rain_prob"], 0.0)
        self.assertEqual(ctx["weather_source"], "injected")

    def test_a_date_the_forecast_does_not_cover_has_no_forecast(self):
        ctx = trip_ctx.build({**DAY, "date": "2026-12-25"}, PROFILE, forecast=self.WEEK,
                             fetch_weather=False)
        self.assertEqual(ctx["weather_source"], "out_of_range")
        self.assertEqual(ctx["rain_prob"], 0.0)
        self.assertEqual(ctx["temp_c"], trip_ctx.DEFAULT_TEMP_C)
        self.assertFalse(trip_ctx.is_wet(ctx))
        self.assertEqual(ctx["weather_date"], "")

    def test_the_second_day_of_an_undated_trip_reads_the_next_day(self):
        # multiday marks the day (`day_offset`); it used to get the first day's rain again.
        first = trip_ctx.build(DAY, PROFILE, forecast=self.WEEK, fetch_weather=False)
        second = trip_ctx.build({**DAY, "day_offset": 1}, PROFILE, forecast=self.WEEK,
                                fetch_weather=False)
        self.assertEqual((first["weather_date"], first["rain_prob"]), ("2026-11-14", 0.0))
        self.assertEqual((second["weather_date"], second["rain_prob"]), ("2026-11-15", 0.9))
        self.assertTrue(first["weather_date_assumed"] and second["weather_date_assumed"])
        beyond = trip_ctx.build({**DAY, "day_offset": 2}, PROFILE, forecast=self.WEEK,
                                fetch_weather=False)
        self.assertEqual(beyond["weather_source"], "out_of_range")

    def test_a_named_date_is_not_an_assumed_one_and_wins_over_the_offset(self):
        ctx = trip_ctx.build({**DAY, "date": "2026-11-14", "day_offset": 1}, PROFILE,
                             forecast=self.WEEK, fetch_weather=False)
        self.assertEqual(ctx["weather_date"], "2026-11-14")
        self.assertFalse(ctx["weather_date_assumed"])

    def test_an_unusable_date_is_no_date(self):
        ctx = trip_ctx.build({**DAY, "date": "thu bay tuan sau"}, PROFILE, forecast=self.WEEK,
                             fetch_weather=False)
        self.assertEqual(ctx["weather_date"], "2026-11-14")
        self.assertTrue(ctx["weather_date_assumed"])


class TestRainExposure(unittest.TestCase):
    def test_rain_cover_decides(self):
        cover = lambda value: {"cat": "restaurant", "weather_sensitive": True,  # noqa: E731
                               "smart_tags": {"rain_cover": value}}
        self.assertEqual(trip_ctx.rain_exposure(cover("enclosed")), 0.0)
        self.assertEqual(trip_ctx.rain_exposure(cover("mixed")), 0.5)
        self.assertEqual(trip_ctx.rain_exposure(cover("open")), 1.0)

    def test_without_it_the_outdoor_exposure_does(self):
        self.assertEqual(trip_ctx.rain_exposure({"cat": "beach"}), 1.0)
        self.assertEqual(trip_ctx.rain_exposure({"cat": "museum"}), 0.0)
        self.assertEqual(trip_ctx.rain_exposure({"cat": "cafe", "weather_sensitive": True}), 1.0)
        self.assertEqual(trip_ctx.rain_exposure(
            {"cat": "cafe", "smart_tags": {"rain_cover": "unknown", "outdoor_exposure": 0.1}}), 0.0)


class TestRainCosts(unittest.TestCase):
    BEACH = {"poi_id": "beach", "cat": "beach"}
    MUSEUM = {"poi_id": "museum", "cat": "museum"}
    PAGODA = {"poi_id": "pagoda", "cat": "temple", "smart_tags": {"rain_cover": "mixed"}}

    def _ctx(self, rain):
        return trip_ctx.build(DAY, PROFILE, forecast=_forecast(rain), fetch_weather=False)

    def test_a_dry_day_costs_nothing_and_cuts_no_band(self):
        ctx = self._ctx(0.2)
        self.assertEqual(trip_ctx.rain_costs(ctx, [self.BEACH, self.MUSEUM]), {})
        self.assertEqual(trip_ctx.state_bands(ctx),
                         [(480, 600), (600, 690), (690, 810), (810, 900), (900, 1080), (1080, 1200)])

    def test_rain_all_day_charges_what_stands_in_it(self):
        ctx = self._ctx(0.9)
        costs = trip_ctx.rain_costs(ctx, [self.BEACH, self.MUSEUM, self.PAGODA])
        bands = range(len(trip_ctx.state_bands(ctx)))
        self.assertEqual({costs[("beach", k)] for k in bands}, {trip_ctx.RAIN_COST_HEAVY})
        self.assertEqual({costs[("pagoda", k)] for k in bands}, {trip_ctx.RAIN_COST_HEAVY * 0.5})
        self.assertFalse([key for key in costs if key[0] == "museum"])

    def test_likely_rain_costs_less_than_near_certain_rain(self):
        costs = trip_ctx.rain_costs(self._ctx(0.6), [self.BEACH])
        self.assertEqual(set(costs.values()), {trip_ctx.RAIN_COST})

    def test_bands_are_cut_where_the_forecast_turns(self):
        ctx = self._ctx(_afternoon_rain)
        bands = trip_ctx.state_bands(ctx)
        self.assertIn((13 * H, 13 * H + 30), bands)   # 11:30-13:30 cut at 13:00
        self.assertIn((15 * H, 18 * H), bands)        # wet as a whole (15, 16, 17 h)
        wet = {k for (pid, k) in trip_ctx.rain_costs(ctx, [self.BEACH])}
        self.assertEqual([bands[k] for k in sorted(wet)],
                         [(13 * H, 13 * H + 30), (13 * H + 30, 15 * H), (15 * H, 18 * H)])


STOPS = [
    StubPOI("beach", visit_min=90, open_min=6 * H, close_min=19 * H, score=5.0, category="beach"),
    StubPOI("museum", visit_min=60, open_min=8 * H, close_min=17 * H, score=4.0, category="museum"),
    StubPOI("cafe", visit_min=45, open_min=7 * H, close_min=22 * H, score=4.0, category="cafe"),
    StubPOI("lunch", visit_min=60, open_min=10 * H, close_min=22 * H, score=4.0,
            restaurant=True, category="restaurant"),
]
TRAVEL = {(a.poi_id, b.poi_id): 10 for a in STOPS for b in STOPS if a is not b}
TRIP = StubTrip(8 * H, 20 * H, None)
BANDS = [(8 * H, 13 * H), (13 * H, 20 * H)]
WET_ALL_DAY = {("beach", 0): 2.0, ("beach", 1): 2.0}
WET_MORNING = {("beach", 0): 2.0}


def _ids(out):
    return [a["poi_id"] for a in out["itinerary"]["activities"]]


class TestSolverUnderRain(unittest.TestCase):
    def test_dry_day_takes_the_beach(self):
        self.assertIn("beach", _ids(optimize(STOPS, TRAVEL, TRIP, workers=1)))

    def test_rain_all_day_leaves_the_beach_out(self):
        out = optimize(STOPS, TRAVEL, TRIP, workers=1, state_bands=BANDS, state_cost=WET_ALL_DAY)
        self.assertNotIn("beach", _ids(out))
        self.assertIn("museum", _ids(out))

    def test_a_named_beach_stays_whatever_the_weather(self):
        out = optimize(STOPS, TRAVEL, TRIP, workers=1, must_visit=["beach"],
                       state_bands=BANDS, state_cost=WET_ALL_DAY)
        self.assertIn("beach", _ids(out))

    def test_a_wet_morning_moves_the_beach_to_the_afternoon(self):
        out = optimize(STOPS, TRAVEL, TRIP, workers=1, state_bands=BANDS, state_cost=WET_MORNING)
        beach = next(a for a in out["itinerary"]["activities"] if a["poi_id"] == "beach")
        self.assertGreaterEqual(int(beach["start"][:2]) * H + int(beach["start"][3:]) + 90 // 4, 13 * H)

    def test_the_seed_does_not_open_a_wet_day_at_the_beach(self):
        dry = _greedy_hint(STOPS, TRAVEL, TRIP, set())
        wet = _greedy_hint(STOPS, TRAVEL, TRIP, set(), state_bands=BANDS, state_cost=WET_ALL_DAY)
        self.assertIn(1, [node for node, _start in dry])      # node 1 = the beach
        self.assertNotIn(1, [node for node, _start in wet])
        self.assertTrue(wet)


class TestRainNote(unittest.TestCase):
    POIS = {"beach": {"poi_id": "beach", "name": "Bai bien", "cat": "beach"},
            "museum": {"poi_id": "museum", "name": "Bao tang", "cat": "museum"}}
    ACTS = [{"poi_id": "museum", "start": "09:00", "end": "10:00"},
            {"poi_id": "beach", "start": "15:00", "end": "16:30"}]

    def _note(self, rain, acts=None, **trip):
        ctx = trip_ctx.build({**DAY, **trip}, PROFILE, forecast=_forecast(rain), fetch_weather=False)
        return trip_ctx.rain_note(ctx, self.ACTS if acts is None else acts, self.POIS)

    def test_a_dry_day_or_an_empty_plan_says_nothing(self):
        self.assertIsNone(self._note(0.2))
        self.assertIsNone(self._note(0.9, acts=[]))

    def test_the_wet_hours_and_what_stays_in_them_are_named(self):
        note = self._note(_afternoon_rain, date="2026-11-14")
        self.assertIn("du bao mua 13:00-18:00 (toi da 90%)", note)
        self.assertIn("Bai bien (15:00, 90%)", note)
        self.assertNotIn("Bao tang", note)          # under a roof, and in a dry hour
        self.assertNotIn("chua co ngay di", note)   # the trip named its date

    def test_a_day_moved_under_a_roof_still_says_why(self):
        note = self._note(0.9, acts=self.ACTS[:1], date="2026-11-14")
        self.assertIn("lich uu tien diem co mai che", note)
        self.assertNotIn("con ngoai troi", note)

    def test_an_undated_trip_says_which_day_it_assumed(self):
        self.assertIn("chua co ngay di nen dung du bao ngay 2026-11-14", self._note(0.9))


class TestPlanSaysWhatStaysInTheRain(unittest.TestCase):
    def _plan(self, rain, **trip):
        day = _trip("08:00", "20:00", **trip)
        ctx = trip_ctx.build(day, day["profile"], forecast=_forecast(rain), fetch_weather=False)
        return build_plan("balanced", day, RANKED, BY_ID, CELLS, template="", ctx=ctx, workers=1)

    def test_a_date_past_the_forecast_is_said_on_the_plan_of_that_day(self):
        plan = self._plan(0.9, date="2026-12-25")
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertTrue(any("chua co du bao thoi tiet cho ngay 2026-12-25" in w
                            for w in plan["warnings"]), plan["warnings"])
        self.assertFalse(any("du bao mua" in w for w in plan["warnings"]))

    def test_a_named_beach_in_the_rain_is_planned_and_named(self):
        plan = self._plan(0.9, must_visit=["beach1"])
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertIn("beach1", [a["poi_id"] for a in plan["activities"]])
        self.assertTrue(any("du bao mua" in w and "BEACH1" in w for w in plan["warnings"]),
                        plan["warnings"])

    def test_without_a_reason_to_be_there_nobody_stands_in_the_rain(self):
        plan = self._plan(0.9)
        self.assertTrue(plan["passed"], plan.get("violations"))
        # ... and the plan says why the beach is missing.
        self.assertTrue(any("du bao mua 08:00-20:00" in w and "mai che" in w
                            for w in plan["warnings"]), plan["warnings"])
        wet = trip_ctx.wet_stops(
            trip_ctx.build(_trip("08:00", "20:00"), PROFILE, forecast=_forecast(0.9), fetch_weather=False),
            plan["activities"], BY_ID)
        outdoor = {"beach1", "nat1", "park1"}
        self.assertFalse(outdoor & {a["poi_id"] for a in plan["activities"]}, plan["activities"])
        self.assertFalse(wet)

    def test_a_dry_forecast_changes_nothing(self):
        plan = self._plan(0.1)
        self.assertFalse(any("du bao mua" in w for w in plan.get("warnings") or []))


if __name__ == "__main__":
    unittest.main()
