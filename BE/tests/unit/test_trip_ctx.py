"""Tests for the trip context + dynamic traveler state (meal-state work).

Covers: conditional meal windows, satiety decay (2.5 h half-life), fatigue
accumulation + heat/dip, UTCI heat bands, the day flags (dip/evening/late),
weather wiring (rain per hour, max for rank, graceful offline fallback) and
the per-POI state multipliers used by rank and the optimizer.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..", "..", "..")))

from BE.app.services import soft_rules  # noqa: E402
from BE.app.services import trip_ctx  # noqa: E402

FULL_DAY = {"start_time": "07:00", "end_time": "21:00"}
MORNING = {"start_time": "07:00", "end_time": "12:00"}
MORNING_LATE = {"start_time": "07:00", "end_time": "13:00"}
AFTERNOON = {"start_time": "13:00", "end_time": "21:00"}
PROFILE = {"party_type": "solo", "pace": 2, "fitness": 2}

FORECAST = {
    "source": "injected", "stale": False,
    "hourly": [
        {"at": f"2026-10-27T{h:02d}:00", "temp_c": t, "rain_prob": r}
        for h, t, r in [
            (7, 27.0, 0.0), (8, 28.0, 0.0), (9, 29.0, 0.1),
            (10, 30.0, 0.1), (11, 31.0, 0.2), (12, 33.0, 0.4),
            (13, 34.0, 0.6), (14, 35.0, 0.8), (15, 34.0, 0.5),
            (16, 33.0, 0.2), (17, 31.0, 0.1), (18, 30.0, 0.0),
            (19, 29.0, 0.0), (20, 28.0, 0.0), (21, 27.0, 0.0),
        ]
    ],
}


class TestMealWindows(unittest.TestCase):
    def test_full_day_has_every_meal(self):
        names = [s["name"] for s in soft_rules.meal_slots(FULL_DAY)]
        self.assertEqual(names, ["breakfast", "snack_morning", "lunch",
                                 "snack_afternoon", "dinner"])

    def test_morning_half_day_has_no_lunch(self):
        """CONDITIONAL meals: a 07-12 trip is not force-fed a lunch."""
        names = [s["name"] for s in soft_rules.meal_slots(MORNING)]
        self.assertNotIn("lunch", names)
        self.assertNotIn("dinner", names)
        self.assertFalse(soft_rules.meal_window_present(MORNING, "lunch"))
        # The templates agree: no forced lunch/rest on that horizon.
        from BE.app.services import templates
        trip = {**MORNING, "profile": PROFILE}
        self.assertFalse(templates.lunch_required(trip))
        self.assertFalse(templates.universal_constraints(trip)["lunch_required"])

    def test_seven_to_thirteen_still_eats_lunch(self):
        """60+ minutes of the 11:30-13:30 window is enough to hold a lunch."""
        self.assertTrue(soft_rules.meal_window_present(MORNING_LATE, "lunch"))

    def test_gate_rest_passes_when_there_is_no_lunch_window(self):
        """The HARD rest check mirrors the conditional meal, not a forced one."""
        from BE.app.services import gate
        trip = {**MORNING, "profile": PROFILE, "budget": 1000000}
        itinerary = {"activities": [{"poi_id": "x", "start": "07:00",
                                     "end": "08:00"}]}
        pois = {"x": {"poi_id": "x", "cat": "cafe", "fee": 0,
                      "verified": True, "opening_hours": []}}
        result = gate.check_rest_follows_lunch(itinerary, trip, pois, {})
        self.assertTrue(result["passed"])

    def test_evening_only_trip_has_dinner_but_no_lunch(self):
        names = [s["name"] for s in soft_rules.meal_slots(AFTERNOON)]
        self.assertNotIn("lunch", names)
        self.assertIn("dinner", names)
        self.assertIn("snack_afternoon", names)


class TestSatiety(unittest.TestCase):
    def test_decays_with_a_2_5h_half_life_after_lunch(self):
        slots = soft_rules.meal_slots(FULL_DAY)
        at_end = trip_ctx.satiety_at(13 * 60 + 30, FULL_DAY, slots)
        two_h = trip_ctx.satiety_at(15 * 60 + 30, FULL_DAY, slots)
        half_life = trip_ctx.satiety_at(16 * 60, FULL_DAY, slots)
        self.assertAlmostEqual(at_end, 1.0, places=3)
        self.assertGreater(two_h, 0.5)          # 120 min < 150 min
        self.assertAlmostEqual(half_life, 0.5, places=2)  # exactly 2.5 h
        self.assertGreater(trip_ctx.satiety_at(14 * 60, FULL_DAY, slots),
                           trip_ctx.satiety_at(17 * 60, FULL_DAY, slots))

    def test_before_lunch_the_traveler_is_hungry(self):
        slots = soft_rules.meal_slots(FULL_DAY)
        self.assertLess(trip_ctx.satiety_at(12 * 60, FULL_DAY, slots), 0.6)

    def test_meal_ends_anchor_the_decay(self):
        slots = soft_rules.meal_slots(FULL_DAY)
        just_after_breakfast = trip_ctx.satiety_at(9 * 60 + 5, FULL_DAY, slots)
        self.assertGreater(just_after_breakfast, 0.9)
        self.assertLess(trip_ctx.satiety_at(11 * 60, FULL_DAY, slots),
                        just_after_breakfast)


class TestFatigueHeatAndFlags(unittest.TestCase):
    def test_fatigue_grows_and_pace_matters(self):
        slow = trip_ctx.fatigue_at(16 * 60, FULL_DAY, {"pace": 1})
        normal = trip_ctx.fatigue_at(16 * 60, FULL_DAY, {"pace": 2})
        fast = trip_ctx.fatigue_at(16 * 60, FULL_DAY, {"pace": 3})
        self.assertLess(slow, normal)
        self.assertLess(normal, fast)
        self.assertLess(trip_ctx.fatigue_at(9 * 60, FULL_DAY, PROFILE),
                        trip_ctx.fatigue_at(18 * 60, FULL_DAY, PROFILE))

    def test_heat_raises_accumulated_fatigue(self):
        cool = trip_ctx.fatigue_at(14 * 60, FULL_DAY, PROFILE, heat=0.0)
        hot = trip_ctx.fatigue_at(14 * 60, FULL_DAY, PROFILE, heat=1.0)
        self.assertGreater(hot, cool)

    def test_heat_bands(self):
        self.assertEqual(trip_ctx.heat_stress(24.0), (0.0, "mat"))
        self.assertEqual(trip_ctx.heat_stress(28.0), (0.35, "am"))
        self.assertEqual(trip_ctx.heat_stress(31.0), (0.6, "nong"))
        self.assertEqual(trip_ctx.heat_stress(33.0), (0.85, "rat nong"))
        self.assertEqual(trip_ctx.heat_stress(36.0), (1.0, "cuc doan"))

    def test_dip_evening_and_late_flags(self):
        dip = trip_ctx.state_at(14 * 60, FULL_DAY, PROFILE)
        self.assertTrue(dip["afternoon_dip"])
        self.assertTrue(dip["light_only"])
        self.assertFalse(trip_ctx.state_at(15 * 60, FULL_DAY, PROFILE)
                         ["afternoon_dip"])
        self.assertTrue(trip_ctx.state_at(19 * 60, FULL_DAY, PROFILE)
                        ["evening_bonus"])
        self.assertTrue(trip_ctx.state_at(21 * 60, FULL_DAY, PROFILE)
                        ["late_night"])


class TestWeatherWiring(unittest.TestCase):
    def test_build_wires_temperature_rain_and_hours(self):
        ctx = trip_ctx.build(FULL_DAY, PROFILE, forecast=FORECAST,
                             fetch_weather=False)
        self.assertEqual(ctx["weather_source"], "injected")
        self.assertEqual(ctx["temp_c"], 35.0)       # max over the trip hours
        self.assertEqual(ctx["rain_prob"], 0.8)     # max rain, the rank safety
        self.assertEqual(len(ctx["hours"]), 15)
        self.assertEqual(ctx["heat_band"], "cuc doan")
        self.assertTrue(ctx["dynamic_state"])
        mid = trip_ctx.state_at(14 * 60, FULL_DAY, PROFILE, ctx)
        self.assertAlmostEqual(mid["rain_prob"], 0.8, places=2)
        self.assertAlmostEqual(mid["temp_c"], 35.0, places=1)

    def test_offline_falls_back_to_the_planning_prior(self):
        ctx = trip_ctx.build(FULL_DAY, PROFILE, fetch_weather=False)
        self.assertEqual(ctx["weather_source"], "none")
        self.assertEqual(ctx["temp_c"], trip_ctx.DEFAULT_TEMP_C)
        self.assertEqual(ctx["rain_prob"], 0.0)
        self.assertEqual(ctx["heat_band"], "nong")  # 30C -> UTCI band "nong"

    def test_no_profile_keeps_state_off(self):
        ctx = trip_ctx.build(FULL_DAY, {}, forecast=FORECAST,
                             fetch_weather=False)
        self.assertFalse(ctx["dynamic_state"])

    def test_optimizer_state_covers_every_band(self):
        ctx = trip_ctx.build(FULL_DAY, PROFILE, forecast=FORECAST,
                             fetch_weather=False)
        bands, scores = trip_ctx.optimizer_state(
            ctx, [{"poi_id": "beach", "cat": "beach", "intensity": 2,
                   "weather_sensitive": True}])
        self.assertTrue(bands)
        for k, (lo, hi) in enumerate(bands):
            self.assertIn(("beach", k), scores)
            self.assertGreaterEqual(scores[("beach", k)], 0.0)
        # The dip band must be the worst one for an outdoor beach.
        self.assertLess(scores[("beach", 3)], scores[("beach", 0)])
        # Disjoint, ordered, inside the horizon.
        for (lo1, hi1), (lo2, hi2) in zip(bands, bands[1:]):
            self.assertLessEqual(hi1, lo2)
        self.assertGreaterEqual(bands[0][0], 7 * 60)
        self.assertLessEqual(bands[-1][1], 21 * 60)


if __name__ == "__main__":
    unittest.main()
