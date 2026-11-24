"""What the app's profile and trip tell the planner (planning_lifecycle._trip_request).

Three leaks closed here:
- spending: `/v1/profile` stores saver/balanced/comfort, but the planner map read
  economy/balanced/premium, so every traveller planned at the middle level;
- outdoor_bias: no product field carried it, so it was always 0; a trip's soft
  `preference_overrides` (stored, never read before) now reach the planner;
- the start of the day: the base the traveller chose (`base_poi_id`) or, on a
  replan, the last stop they finished becomes `TripRequest.origin`.

Run: python -m pytest BE/tests/unit/test_planning_profile_pipe.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from pydantic import ValidationError  # noqa: E402

from BE.app.modules.planning_lifecycle.api import ConstraintOverrides  # noqa: E402
from BE.app.modules.planning_lifecycle.service import (  # noqa: E402
    _current_poi,
    _effective_profile,
    _profile,
    _trip_request,
)

PROFILE = {
    "party_type": "couple", "trip_purpose": "leisure", "pace": 1, "fitness": 3,
    "spending_style": "comfort", "food_preferences": ["hải sản"],
    "preferred_activities": ["biển"], "usual_transport": [], "must_avoid": [],
    "allergies": ["đậu phộng"], "accessibility_needs": [],
}
TRIP = {
    "id": "t1", "start_date": "2026-11-28", "day_start": "08:00:00", "day_end": "20:00:00",
    "traveler_count": 2, "indicative_budget": 2000000, "preferred_transport": "motorbike",
    "profile_snapshot": PROFILE, "preference_overrides": {},
}


class TestSpendingLevel(unittest.TestCase):
    def test_the_styles_the_profile_api_stores(self):
        for style, level in (("saver", 1), ("balanced", 2), ("comfort", 3)):
            self.assertEqual(_profile({"spending_style": style})["spending_level"], level)

    def test_the_older_names_still_map(self):
        self.assertEqual(_profile({"spending_style": "economy"})["spending_level"], 1)
        self.assertEqual(_profile({"spending_style": "premium"})["spending_level"], 3)

    def test_an_unknown_style_is_the_middle(self):
        self.assertEqual(_profile({"spending_style": "lavish"})["spending_level"], 2)
        self.assertEqual(_profile({})["spending_level"], 2)

    def test_a_level_wins_over_a_style(self):
        self.assertEqual(_profile({"spending_level": 1, "spending_style": "comfort"})["spending_level"], 1)


class TestLevelsAndBias(unittest.TestCase):
    def test_pace_and_fitness_pass_through(self):
        profile = _profile(PROFILE)
        self.assertEqual((profile["pace"], profile["fitness"]), (1, 3))

    def test_an_out_of_range_answer_is_neutral(self):
        profile = _profile({"pace": 7, "fitness": "fast", "outdoor_bias": "x"})
        self.assertEqual((profile["pace"], profile["fitness"], profile["outdoor_bias"]), (2, 2, 0.0))

    def test_outdoor_bias_is_clamped(self):
        self.assertEqual(_profile({"outdoor_bias": 1.7})["outdoor_bias"], 1.0)
        self.assertEqual(_profile({"outdoor_bias": -0.5})["outdoor_bias"], -0.5)
        self.assertEqual(_profile({})["outdoor_bias"], 0.0)


class TestTripOverrides(unittest.TestCase):
    def test_soft_overrides_change_the_profile(self):
        snapshot = {**TRIP, "preference_overrides": {"outdoor_bias": 0.5, "pace": 3}}
        profile = _effective_profile(snapshot)
        self.assertEqual((profile["outdoor_bias"], profile["pace"]), (0.5, 3))

    def test_hard_fields_never_come_from_overrides(self):
        snapshot = {**TRIP, "preference_overrides": {"allergies": [], "must_avoid": ["chùa"]}}
        profile = _effective_profile(snapshot)
        self.assertEqual(profile["allergies"], ["đậu phộng"])
        self.assertEqual(profile["must_avoid"], [])


class TestTripRequest(unittest.TestCase):
    def test_the_profile_reaches_the_planner(self):
        profile = _trip_request({**TRIP, "preference_overrides": {"outdoor_bias": 0.5}}, {})["profile"]
        self.assertEqual(profile["spending_level"], 3)
        self.assertEqual(profile["outdoor_bias"], 0.5)
        self.assertEqual(profile["fitness"], 3)

    def test_no_base_keeps_the_open_tour(self):
        self.assertIsNone(_trip_request(TRIP, {})["origin"])

    def test_the_day_starts_at_the_chosen_base(self):
        origin = _trip_request({**TRIP, "base_poi_id": "hotel"}, {})["origin"]
        self.assertEqual(origin["poi_id"], "hotel")

    def test_saved_base_applies_until_the_traveler_finishes_a_stop(self):
        snapshot = {**TRIP, "preference_overrides": {"base_poi_id": "hotel"}}
        self.assertEqual(_trip_request(snapshot, {})["origin"]["poi_id"], "hotel")
        self.assertEqual(
            _trip_request(snapshot, {"current_poi_id": "cafe"})["origin"]["poi_id"], "cafe"
        )

    def test_a_replan_resumes_from_the_last_finished_stop(self):
        trip = _trip_request({**TRIP, "base_poi_id": "hotel"},
                             {"current_poi_id": "cafe", "remaining_from": "14:10"})
        self.assertEqual(trip["origin"]["poi_id"], "cafe")
        self.assertEqual(trip["start_time"], "14:10")


class TestCurrentPoi(unittest.TestCase):
    KNOWN = {
        "a1": {"poi_id": "market", "order": (0, 0)},
        "a2": {"poi_id": "cafe", "order": (0, 2)},
        "a3": {"poi_id": None, "order": (0, 3)},
        "b1": {"poi_id": "beach", "order": (1, 0)},
    }

    def test_the_latest_finished_stop(self):
        self.assertEqual(_current_poi(["a2", "a1"], self.KNOWN), "cafe")
        self.assertEqual(_current_poi(["a1", "b1", "a2"], self.KNOWN), "beach")

    def test_a_custom_activity_has_no_place(self):
        self.assertEqual(_current_poi(["a1", "a3"], self.KNOWN), "market")

    def test_nothing_done_yet(self):
        self.assertIsNone(_current_poi([], self.KNOWN))


class TestOverridesContract(unittest.TestCase):
    def test_the_app_may_send_a_base(self):
        self.assertEqual(ConstraintOverrides(base_poi_id="hotel").base_poi_id, "hotel")

    def test_an_empty_base_is_refused(self):
        with self.assertRaises(ValidationError):
            ConstraintOverrides(base_poi_id="")


if __name__ == "__main__":
    unittest.main()
