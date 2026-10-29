"""Unit tests for the layer-1 soft rules (A2/B1/B2/E2) and their wiring.

A2/B1 are pair-level (fed to the optimizer through scorer.edge_scores);
B2/E2 are sequence-level and reported per plan. None of them is a gate.

Run from repo root: PYTHONPATH=BE python -m unittest BE.tests.unit.test_soft_rules
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import scorer, soft_rules  # noqa: E402

POIS = {
    "r1": {"poi_id": "r1", "cat": "restaurant", "type": "Nhà hàng hải sản",
           "rating": 4.8, "fee": 0, "visit_min": {"p50": 60}, "intensity": 1},
    "r2": {"poi_id": "r2", "cat": "restaurant", "type": "Nhà hàng Việt Nam",
           "rating": 4.7, "fee": 0, "visit_min": {"p50": 60}, "intensity": 1},
    "cafe1": {"poi_id": "cafe1", "cat": "cafe", "type": "Quán cà phê",
              "rating": 4.9, "fee": 0, "visit_min": {"p50": 45}, "intensity": 1},
    "cafe2": {"poi_id": "cafe2", "cat": "cafe", "type": "Quán cà phê",
              "rating": 4.8, "fee": 0, "visit_min": {"p50": 45}, "intensity": 1},
    "cafe3": {"poi_id": "cafe3", "cat": "cafe", "type": "Quán cà phê",
              "rating": 4.7, "fee": 0, "visit_min": {"p50": 45}, "intensity": 1},
    "cafe4": {"poi_id": "cafe4", "cat": "cafe", "type": "Quán cà phê",
              "rating": 4.6, "fee": 0, "visit_min": {"p50": 45}, "intensity": 1},
    "view": {"poi_id": "view", "cat": "viewpoint", "type": "Điểm ngắm cảnh",
             "rating": 4.7, "fee": 0, "visit_min": {"p50": 30}, "intensity": 1},
    "sunset": {"poi_id": "sunset", "cat": "sunset_view", "type": "Điểm ngắm cảnh",
               "rating": 4.8, "fee": 0, "visit_min": {"p50": 30}, "intensity": 1},
    "bar": {"poi_id": "bar", "cat": "bar", "type": "Quán bar",
            "rating": 4.6, "fee": 0, "visit_min": {"p50": 60}, "intensity": 2},
    "beach": {"poi_id": "beach", "cat": "beach", "type": "Bãi biển",
              "rating": 4.7, "fee": 0, "visit_min": {"p50": 60}, "intensity": 2},
}


def act(poi_id, start, end):
    return {"poi_id": poi_id, "start": start, "end": end}


class TestEdgePenalty(unittest.TestCase):
    def test_a2_back_to_back_restaurants_penalized(self):
        penalty = soft_rules.edge_penalty(POIS["r1"], POIS["r2"])
        self.assertLess(penalty, 0)
        self.assertEqual(penalty, -(soft_rules.SAME_TYPE_PENALTY
                                    + soft_rules.RESTAURANT_PAIR_PENALTY))

    def test_b1_same_type_consecutive_penalized(self):
        penalty = soft_rules.edge_penalty(POIS["beach"], POIS["beach"])
        self.assertEqual(penalty, -soft_rules.SAME_TYPE_PENALTY)

    def test_b1_cafe_to_cafe_is_exempt(self):
        self.assertEqual(soft_rules.edge_penalty(POIS["cafe1"], POIS["cafe2"]), 0.0)

    def test_b1_viewpoint_to_sunset_view_is_exempt(self):
        self.assertEqual(soft_rules.edge_penalty(POIS["view"], POIS["sunset"]), 0.0)

    def test_different_types_have_no_edge_penalty(self):
        self.assertEqual(soft_rules.edge_penalty(POIS["beach"], POIS["r1"]), 0.0)

    def test_edge_scores_include_the_soft_penalty(self):
        """A2/B1 reach the optimizer: same-type edges score lower."""
        q = scorer.edge_scores(["r1", "r2", "beach"], POIS)
        base = scorer.score_transition(POIS["r1"], POIS["r2"])
        expected = round(base + soft_rules.edge_penalty(POIS["r1"], POIS["r2"]), 4)
        self.assertEqual(q[("r1", "r2")], expected)
        self.assertLess(q[("r1", "r2")], base)
        # Different-type edge carries no soft penalty.
        self.assertEqual(q[("r1", "beach")],
                         round(scorer.score_transition(POIS["r1"], POIS["beach"]), 4))


class TestPlanPenalties(unittest.TestCase):
    def test_f1_food_and_sightseeing_categories(self):
        self.assertTrue(soft_rules.is_food(POIS["r1"]))
        self.assertTrue(soft_rules.is_food(POIS["cafe1"]))
        self.assertTrue(soft_rules.is_sightseeing(POIS["view"]))
        self.assertTrue(soft_rules.is_sightseeing(POIS["beach"]))
        self.assertFalse(soft_rules.is_food(POIS["bar"]))
        self.assertFalse(soft_rules.is_sightseeing(POIS["bar"]))

    def test_a2_restaurants_under_2h5_across_slots_flagged(self):
        acts = [act("r1", "09:30", "10:30"), act("r2", "11:30", "12:30")]
        report = soft_rules.plan_penalties(acts, POIS)
        self.assertIn("A2", [i["rule"] for i in report["issues"]])
        self.assertGreater(report["penalty"], 0)

    def test_a2_restaurants_far_apart_not_flagged(self):
        acts = [act("r1", "08:00", "09:00"), act("r2", "14:00", "15:00")]
        report = soft_rules.plan_penalties(acts, POIS)
        self.assertNotIn("A2", [i["rule"] for i in report["issues"]])

    def test_b1_consecutive_same_type_flagged(self):
        acts = [act("beach", "08:00", "09:00"), act("beach", "09:30", "10:30")]
        report = soft_rules.plan_penalties(acts, POIS)
        self.assertIn("B1", [i["rule"] for i in report["issues"]])

    def test_b1_cafe_to_cafe_not_flagged(self):
        acts = [act("cafe1", "07:00", "07:45"), act("cafe2", "08:00", "08:45")]
        report = soft_rules.plan_penalties(acts, POIS)
        self.assertNotIn("B1", [i["rule"] for i in report["issues"]])

    def test_b2_more_than_two_same_type_penalty_increases(self):
        three = [act("cafe1", "07:00", "07:45"), act("cafe2", "08:00", "08:45"),
                 act("cafe3", "09:00", "09:45")]
        four = three + [act("cafe4", "10:00", "10:45")]
        p3 = soft_rules.plan_penalties(three, POIS)["penalty"]
        p4 = soft_rules.plan_penalties(four, POIS)["penalty"]
        self.assertIn("B2", [i["rule"] for i in soft_rules.plan_penalties(three, POIS)["issues"]])
        self.assertGreater(p4, p3)  # third costs a step, fourth costs two

    def test_b2_two_same_type_not_flagged(self):
        acts = [act("beach", "08:00", "09:00"), act("beach", "10:00", "11:00")]
        rules = [i["rule"] for i in soft_rules.plan_penalties(acts, POIS)["issues"]]
        self.assertNotIn("B2", rules)

    def test_e2_bar_before_17_flagged(self):
        report = soft_rules.plan_penalties([act("bar", "09:00", "10:00")], POIS)
        self.assertIn("E2", [i["rule"] for i in report["issues"]])

    def test_e2_bar_evening_not_flagged(self):
        report = soft_rules.plan_penalties([act("bar", "19:00", "20:00")], POIS)
        self.assertNotIn("E2", [i["rule"] for i in report["issues"]])

    def test_clean_plan_has_zero_penalty(self):
        acts = [act("cafe1", "07:00", "07:45"), act("beach", "08:30", "09:30"),
                act("r1", "11:30", "12:30"), act("view", "16:00", "16:30")]
        report = soft_rules.plan_penalties(acts, POIS)
        self.assertEqual(report, {"penalty": 0.0, "issues": []})


class TestRestFollowsLunch(unittest.TestCase):
    """Rest window START = lunch END, length by pace, late-lunch shrink."""

    PROFILE = {"party_type": "solo", "pace": 2}

    def test_rest_starts_at_lunch_end(self):
        acts = [act("r1", "11:30", "12:30"), act("beach", "10:00", "11:00")]
        span = soft_rules.rest_span(acts, POIS, self.PROFILE, 18 * 60)
        self.assertEqual(span["start"], 12 * 60 + 30)
        self.assertEqual(span["end"], 13 * 60 + 15)  # pace 2 -> 45
        self.assertEqual(span["requested_minutes"], 45)
        self.assertFalse(span["shrunk"])
        self.assertEqual(span["lunch_poi_id"], "r1")

    def test_rest_length_follows_pace(self):
        acts = [act("r1", "11:30", "12:30")]
        for pace, minutes in {1: 60, 2: 45, 3: 30}.items():
            span = soft_rules.rest_span(acts, POIS, {"pace": pace}, 18 * 60)
            self.assertEqual(span["minutes"], minutes, pace)

    def test_late_lunch_shrinks_to_fit_but_never_below_floor(self):
        # Lunch starts 12:50 (valid) but lasts to 15:10 -> a late lunch.
        late = [act("r1", "12:50", "15:10")]
        span = soft_rules.rest_span(late, POIS, self.PROFILE, 15 * 60 + 40)
        self.assertTrue(span["shrunk"])
        self.assertEqual(span["start"], 15 * 60 + 10)
        self.assertEqual(span["minutes"], 30)      # fits 15:10 -> 15:40
        self.assertEqual(span["requested_minutes"], 45)
        tiny = soft_rules.rest_span(late, POIS, self.PROFILE, 15 * 60 + 20)
        self.assertGreaterEqual(tiny["minutes"], soft_rules.REST_MIN_FLOOR)
        self.assertEqual(tiny["minutes"], soft_rules.REST_MIN_FLOOR)

    def test_no_lunch_means_no_rest_window(self):
        acts = [act("beach", "10:00", "11:00")]
        self.assertIsNone(soft_rules.rest_span(acts, POIS, self.PROFILE, 18 * 60))


if __name__ == "__main__":
    unittest.main()
