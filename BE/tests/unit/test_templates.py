"""Unit tests for the 3 hard day templates + profile -> template selection.

Run: python -m pytest BE/tests/unit/test_templates.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.templates import (  # noqa: E402
    DAY_TEMPLATES,
    attempts,
    allows,
    select_template,
    template_constraints,
    universal_constraints,
)

NEUTRAL = {"party_type": "solo", "pace": 2, "fitness": 2}


class TestSelection(unittest.TestCase):
    def test_three_hard_templates(self):
        self.assertEqual(set(DAY_TEMPLATES),
                         {"family-slow", "friends-fast", "couple-calm"})

    def test_party_type_drives_selection(self):
        self.assertEqual(select_template({"party_type": "family"}), "family-slow")
        self.assertEqual(select_template({"party_type": "gia đình"}),
                         "family-slow")
        self.assertEqual(select_template({"party_type": "friends"}),
                         "friends-fast")
        self.assertEqual(select_template({"party_type": "nhóm bạn"}),
                         "friends-fast")
        self.assertEqual(select_template({"party_type": "couple"}),
                         "couple-calm")

    def test_pace_fitness_fallbacks(self):
        self.assertEqual(select_template({**NEUTRAL, "pace": 3}), "friends-fast")
        self.assertEqual(select_template({**NEUTRAL, "fitness": 3}),
                         "friends-fast")
        self.assertEqual(select_template({**NEUTRAL, "fitness": 1}),
                         "family-slow")
        self.assertEqual(select_template({**NEUTRAL, "activities": ["nightlife"]}),
                         "friends-fast")
        self.assertEqual(select_template(NEUTRAL), "couple-calm")
        self.assertEqual(select_template({}), "couple-calm")

    def test_accessibility_caps_pace(self):
        """A stroller/wheelchair answer makes a pace-3 day slow, not fast."""
        profile = {**NEUTRAL, "pace": 3, "accessibility": ["stroller"]}
        self.assertEqual(select_template(profile), "couple-calm")
        # family + accessibility stays family
        self.assertEqual(select_template({"party_type": "family",
                                          "accessibility": ["wheelchair"]}),
                         "family-slow")

    def test_party_type_beats_pace(self):
        self.assertEqual(select_template({"party_type": "family", "pace": 3}),
                         "family-slow")


class TestTemplateShape(unittest.TestCase):
    def test_slots_ordered_with_hints(self):
        for name, template in DAY_TEMPLATES.items():
            hints = [slot["start_hint"] for slot in template["slots"]]
            self.assertEqual(hints, sorted(hints), name)
            for slot in template["slots"]:
                self.assertIn("type", slot, name)
                self.assertRegex(slot["start_hint"], r"^\d{2}:\d{2}$", name)

    def test_family_has_locked_lunch_rest(self):
        family = DAY_TEMPLATES["family-slow"]
        self.assertEqual(family["rest_block"]["minutes"], 60)
        self.assertNotIn("start", family["rest_block"])  # follows lunch
        self.assertEqual(family["pace_stops"], (5, 6))
        self.assertNotIn("bar", family["allowed_categories"])
        self.assertNotIn("nature", family["allowed_categories"])  # no trek
        self.assertLessEqual(family["max_intensity"], 2)
        # lunch slot exists before the rest block
        types = [slot["type"] for slot in family["slots"]]
        self.assertIn("restaurant", types)
        self.assertLess(types.index("restaurant"),
                        types.index("park"))

    def test_friends_allows_nightlife_and_late_end(self):
        friends = DAY_TEMPLATES["friends-fast"]
        self.assertEqual(friends["pace_stops"], (7, 8))
        self.assertIn("bar", friends["allowed_categories"])
        self.assertEqual(friends["late_end_min"], 20 * 60)
        # Universal rest: every template locks a post-lunch window.
        self.assertEqual(friends["rest_block"]["minutes"], 30)
        self.assertNotIn("start", friends["rest_block"])

    def test_couple_is_six_stops_culture_food(self):
        couple = DAY_TEMPLATES["couple-calm"]
        self.assertEqual(couple["pace_stops"], (6, 6))
        types = {slot["type"] for slot in couple["slots"]}
        self.assertTrue(types & {"museum", "landmark", "attraction"})
        self.assertIn("restaurant", types)
        self.assertNotIn("bar", couple["allowed_categories"])


class TestConstraints(unittest.TestCase):
    def test_family_rest_length_and_bands(self):
        limits = template_constraints("family-slow",
                                      {"start_time": "08:00",
                                       "end_time": "17:30"})
        self.assertIsNone(limits["blocked_window"])  # no fixed clock anchor
        self.assertTrue(limits["rest_after_lunch"])
        self.assertEqual(limits["rest_minutes"], 60)
        self.assertEqual((limits["min_stops"], limits["max_stops"]), (5, 6))
        self.assertEqual(limits["max_intensity"], 2)
        self.assertIsNone(limits["late_end_min"])

    def test_rest_follows_lunch_dropped_outside_horizon(self):
        limits = template_constraints("family-slow",
                                      {"start_time": "07:00",
                                       "end_time": "11:00"})
        self.assertIsNone(limits["blocked_window"])
        self.assertFalse(limits["rest_after_lunch"])
        self.assertIsNone(limits["rest_minutes"])

    def test_late_end_only_when_horizon_allows(self):
        long = template_constraints("friends-fast",
                                    {"start_time": "08:00",
                                     "end_time": "22:00"})
        self.assertEqual(long["late_end_min"], 20 * 60)
        short = template_constraints("friends-fast",
                                     {"start_time": "08:00",
                                      "end_time": "18:00"})
        self.assertIsNone(short["late_end_min"])

    def test_attempts_relax_counts_not_archetype(self):
        full = template_constraints("family-slow",
                                    {"start_time": "08:00",
                                     "end_time": "17:30",
                                     "profile": {"pace": 1}})
        ladder = attempts(full)
        self.assertEqual(len(ladder), 3)
        self.assertEqual(ladder[0]["min_stops"], 5)
        self.assertIsNone(ladder[1]["min_stops"])
        self.assertEqual(ladder[1]["required_any"], [])
        self.assertIsNone(ladder[2]["max_stops"])
        for step in ladder:  # the lunch+rest rule + bans never relax
            self.assertIsNone(step["blocked_window"])
            self.assertTrue(step["rest_after_lunch"])
            self.assertEqual(step["rest_minutes"], 60)  # pace 1
            self.assertEqual(step["allowed_categories"],
                             full["allowed_categories"])
            self.assertTrue(step["lunch_required"])

    def test_allows_respects_bans(self):
        self.assertTrue(allows({"cat": "cafe", "intensity": 1}, "family-slow"))
        self.assertFalse(allows({"cat": "bar", "intensity": 1}, "family-slow"))
        self.assertFalse(allows({"cat": "nature", "intensity": 1}, "family-slow"))
        self.assertFalse(allows({"cat": "cafe", "intensity": 3}, "family-slow"))
        self.assertTrue(allows({"cat": "bar", "intensity": 3}, "friends-fast"))


TRIP_LONG = {"start_time": "08:00", "end_time": "18:00",
             "profile": {"party_type": "solo", "pace": 2, "fitness": 2}}


class TestUniversalRestAndLunch(unittest.TestCase):
    """Lunch + rest are human needs: they hold for EVERY template/profile."""

    def test_every_template_has_a_rest_block(self):
        for name, template in DAY_TEMPLATES.items():
            block = template.get("rest_block")
            self.assertIsNotNone(block, name)
            self.assertIsNone(block.get("start"), name)  # follows lunch end
            self.assertIn(block["minutes"], (30, 45, 60), name)
            limits = template_constraints(name, TRIP_LONG)
            self.assertTrue(limits["rest_after_lunch"], name)
            self.assertIsNone(limits["blocked_window"], name)
            self.assertTrue(limits["lunch_required"], name)
            self.assertIn(limits["rest_minutes"], (30, 45, 60), name)

    def test_rest_length_follows_pace(self):
        expected = {1: 60, 2: 45, 3: 30}
        for pace, minutes in expected.items():
            trip = {**TRIP_LONG, "profile": {**TRIP_LONG["profile"],
                                             "pace": pace}}
            limits = template_constraints("couple-calm", trip)
            self.assertTrue(limits["rest_after_lunch"], pace)
            self.assertEqual(limits["rest_minutes"], minutes, pace)

    def test_lunch_required_only_when_horizon_can_hold_it(self):
        short = {**TRIP_LONG, "start_time": "07:00", "end_time": "10:00"}
        self.assertFalse(template_constraints("couple-calm", short)
                         ["lunch_required"])
        self.assertFalse(template_constraints("couple-calm", short)
                         ["rest_after_lunch"])
        self.assertIsNone(template_constraints("couple-calm", short)
                          ["rest_minutes"])

    def test_custom_profile_without_archetype_still_gets_rest(self):
        """No archetype name -> the universal lunch + rest rule still applies."""
        limits = universal_constraints(TRIP_LONG)
        self.assertTrue(limits["rest_after_lunch"])
        self.assertTrue(limits["lunch_required"])
        self.assertEqual(limits["rest_minutes"], 45)  # pace 2
        self.assertIsNone(limits["blocked_window"])
        self.assertIsNone(limits["min_stops"])
        self.assertIsNone(limits["allowed_categories"])

    def test_legacy_without_profile_has_no_universal_constraints(self):
        limits = universal_constraints({"start_time": "08:00",
                                        "end_time": "18:00"})
        self.assertFalse(limits["rest_after_lunch"])
        self.assertIsNone(limits["rest_minutes"])
        self.assertFalse(limits["lunch_required"])


if __name__ == "__main__":
    unittest.main()
