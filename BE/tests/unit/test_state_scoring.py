"""Tests for the state-driven soft scoring (rank + edge + optimizer bands).

One rule per test: satiety suppresses food, fatigue penalizes trek and
prefers rest, heat shifts indoors, the 13-15 dip keeps only light/indoor,
the evening adds the social/food bonus, the transition scorer gets the
satiety-aware food penalty, and the optimizer places a stop OUT of a bad
band (the part rank alone cannot do).
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..", "..", "..")))

from BE.app.services import optimizer, rank, scorer, soft_rules, trip_ctx  # noqa: E402

FULL_DAY = {"start_time": "07:00", "end_time": "21:00",
            "budget": 2000000}
PROFILE = {"party_type": "solo", "pace": 2, "fitness": 2}

RESTAURANT = {"poi_id": "r1", "cat": "restaurant", "rating": 4.6,
              "fee": 100000, "intensity": 1, "tags": ["Hải sản"]}
CAFE = {"poi_id": "c1", "cat": "cafe", "rating": 4.6, "fee": 50000,
        "intensity": 1, "tags": ["Quán cà phê"]}
BEACH = {"poi_id": "b1", "cat": "beach", "rating": 4.6, "intensity": 2,
         "weather_sensitive": True, "tags": ["Bãi biển"]}
TREK = {"poi_id": "t1", "cat": "nature", "rating": 4.6, "intensity": 3,
        "weather_sensitive": True, "tags": ["trekking", "núi"]}
MUSEUM = {"poi_id": "m1", "cat": "museum", "rating": 4.6, "intensity": 1,
          "weather_sensitive": False, "tags": ["Bảo tàng"]}
MARKET = {"poi_id": "k1", "cat": "market", "rating": 4.6, "intensity": 1,
          "weather_sensitive": True, "tags": ["Chợ đêm"]}
BAR = {"poi_id": "n1", "cat": "bar", "rating": 4.6, "intensity": 1,
       "weather_sensitive": False, "tags": ["Bar"]}


def _ctx(hour="12:00", **extra):
    return {"dynamic_state": True, "trip": FULL_DAY, "profile": PROFILE,
            "meal_slots": soft_rules.meal_slots(FULL_DAY), "hour": hour,
            **extra}


def _minutes(hour: str) -> int:
    h, m = hour.split(":")
    return int(h) * 60 + int(m)


NEUTRAL = {
    "satiety": 0.0, "fatigue": 0.0, "heat_stress": 0.0, "afternoon_dip": False,
    "evening_bonus": False, "late_night": False, "light_only": False,
    "heat_band": "mat", "temp_c": 25.0, "rain_prob": 0.0,
}


def _mult(poi, hour, **extra):
    """Real state at a real hour (integration-level multiplier)."""
    ctx = _ctx(hour, **extra)
    state = trip_ctx.state_at(_minutes(hour), FULL_DAY, PROFILE, ctx)
    return trip_ctx.poi_multiplier(poi, state, PROFILE)


def _rule(poi, **state):
    """Isolated rule: one synthetic state, no other state stacked on top."""
    return trip_ctx.poi_multiplier(poi, {**NEUTRAL, **state}, PROFILE)


class TestSatietyRule(unittest.TestCase):
    def test_full_suppresses_a_restaurant(self):
        mult, reasons = _rule(RESTAURANT, satiety=0.9)
        self.assertAlmostEqual(mult, trip_ctx.FOOD_FULL_RESTAURANT, places=3)
        self.assertIn("no, vua an xong", reasons)

    def test_full_only_discounts_a_cafe(self):
        mult, _ = _rule(CAFE, satiety=0.9)
        self.assertAlmostEqual(mult, trip_ctx.FOOD_FULL_CAFE, places=3)

    def test_hungry_before_lunch_keeps_food_attractive(self):
        mult, reasons = _rule(RESTAURANT, satiety=0.1)
        self.assertAlmostEqual(mult, trip_ctx.FOOD_HUNGRY, places=3)
        self.assertIn("doi, hop bua an", reasons)

    def test_real_post_lunch_state_suppresses_food(self):
        restaurant, reasons = _mult(RESTAURANT, "13:40")
        cafe, _ = _mult(CAFE, "13:40")
        self.assertIn("no, vua an xong", reasons)
        self.assertLess(restaurant, cafe)

    def test_breakfast_cafe_is_the_meal_not_an_extra(self):
        """Inside 07:00-09:00 the morning cafe is breakfast: not discounted."""
        state = trip_ctx.state_at(7 * 60 + 30, FULL_DAY, PROFILE,
                                  _ctx("07:30", temp_c=26.0))
        self.assertEqual(state["meal_window"], "breakfast")
        mult, reasons = trip_ctx.poi_multiplier(CAFE, state, PROFILE)
        self.assertEqual(mult, 1.0)
        self.assertNotIn("vua an, chi hop do nhe", reasons)

    def test_rank_score_drops_when_full(self):
        full = rank.score_poi(RESTAURANT, {}, _ctx("13:40"))
        hungry = rank.score_poi(RESTAURANT, {}, _ctx("11:00"))
        self.assertLess(full["score"], hungry["score"])

    def test_legacy_ctx_has_no_state_multiplier(self):
        """No dynamic_state -> the exact previous single-hour score."""
        one = rank.score_poi(RESTAURANT, {}, {"hour": "13:40"})
        two = rank.score_poi(RESTAURANT, {}, {"hour": "11:00"})
        self.assertEqual(one["score"], two["score"])


class TestFatigueRule(unittest.TestCase):
    def test_tired_penalizes_trek_and_prefers_rest(self):
        trek_mult, trek_reasons = _rule(TREK, fatigue=0.7)
        cafe_mult, cafe_reasons = _rule(CAFE, fatigue=0.7)
        self.assertAlmostEqual(trek_mult, trip_ctx.FATIGUE_TREK, places=3)
        self.assertAlmostEqual(cafe_mult, trip_ctx.FATIGUE_REST, places=3)
        self.assertIn("met, giam di bo/leo", trek_reasons)
        self.assertIn("met, uu tien cho nghi", cafe_reasons)

    def test_fresh_traveler_has_no_penalty(self):
        mult, reasons = _rule(TREK)
        self.assertEqual(mult, 1.0)
        self.assertNotIn("met, giam di bo/leo", reasons)

    def test_real_late_afternoon_is_tired(self):
        # pace 3: 10.5 h of walking at 17:30 -> fatigue > 0.6.
        ctx = _ctx("17:30", temp_c=27.0)
        ctx["profile"] = {"party_type": "solo", "pace": 3, "fitness": 3}
        state = trip_ctx.state_at(_minutes("17:30"), FULL_DAY, ctx["profile"],
                                  ctx)
        self.assertGreater(state["fatigue"], 0.6)
        trek, reasons = trip_ctx.poi_multiplier(TREK, state, ctx["profile"])
        self.assertLess(trek, 1.0)
        self.assertIn("met, giam di bo/leo", reasons)


class TestHeatRule(unittest.TestCase):
    def test_hot_hour_pushes_indoor(self):
        outdoor, outdoor_reasons = _rule(BEACH, heat_stress=0.85,
                                         heat_band="rat nong")
        indoor, _ = _rule(MUSEUM, heat_stress=0.85, heat_band="rat nong")
        self.assertAlmostEqual(outdoor, trip_ctx.HEAT_OUTDOOR, places=3)
        self.assertAlmostEqual(indoor, trip_ctx.HEAT_INDOOR, places=3)
        self.assertTrue(any("tranh ngoai troi" in r for r in outdoor_reasons))

    def test_cool_morning_leaves_outdoor_alone(self):
        mult, _ = _rule(BEACH, heat_stress=0.0)
        self.assertEqual(mult, 1.0)

    def test_real_hot_midday_moves_atraight_outdoors_option_down(self):
        # 12:00 at 34C (injected): beach below a museum at the same hour.
        beach, beach_reasons = _mult(BEACH, "12:00", temp_c=34.0)
        museum, _ = _mult(MUSEUM, "12:00", temp_c=34.0)
        self.assertLess(beach, museum)
        self.assertTrue(any("tranh ngoai troi" in r for r in beach_reasons))


class TestDipRule(unittest.TestCase):
    def test_dip_keeps_only_light_indoor_options(self):
        heavy, heavy_reasons = _rule(BEACH, afternoon_dip=True)
        light, light_reasons = _rule(CAFE, afternoon_dip=True)
        self.assertAlmostEqual(heavy, trip_ctx.DIP_HEAVY, places=3)
        self.assertAlmostEqual(light, trip_ctx.DIP_LIGHT, places=3)
        self.assertIn("dip chieu, chi di nhe", heavy_reasons)
        self.assertIn("dip chieu, hop cho nhe", light_reasons)

    def test_real_dip_window_prefers_light(self):
        beach, _ = _mult(BEACH, "14:00", temp_c=26.0)
        cafe, _ = _mult(CAFE, "14:00", temp_c=26.0)
        self.assertLess(beach, cafe)

    def test_dip_ends_at_15(self):
        state = trip_ctx.state_at(15 * 60 + 1, FULL_DAY, PROFILE,
                                  _ctx("15:01", temp_c=28.0))
        self.assertFalse(state["afternoon_dip"])
        self.assertEqual(trip_ctx.poi_multiplier(BEACH, state)[0], 1.0)


class TestEveningRule(unittest.TestCase):
    def test_evening_food_bonus(self):
        # satiety 0.5 isolates the evening rule (hungry bonus is < 0.35).
        mult, reasons = _rule(RESTAURANT, evening_bonus=True, satiety=0.5)
        self.assertAlmostEqual(mult, trip_ctx.EVENING_SOCIAL, places=3)
        self.assertIn("toi, hop an uong/xa hoi", reasons)
        self.assertAlmostEqual(_rule(BAR, evening_bonus=True, satiety=0.5)[0],
                               trip_ctx.EVENING_SOCIAL, places=3)

    def test_nothing_heavy_after_21(self):
        mult, reasons = _rule(RESTAURANT, evening_bonus=True,
                              late_night=True, satiety=0.2)
        # heavy cutoff, evening social and the dinner-hunger nudge all apply
        self.assertLessEqual(mult, trip_ctx.LATE_HEAVY
                             * trip_ctx.EVENING_SOCIAL
                             * trip_ctx.FOOD_HUNGRY)
        self.assertIn("sau 21h, tranh bua nang", reasons)

    def test_real_1900_is_dinner_time(self):
        state = trip_ctx.state_at(19 * 60, FULL_DAY, PROFILE,
                                  _ctx("19:00", temp_c=28.0))
        self.assertTrue(state["evening_bonus"])
        self.assertLess(state["satiety"], 0.35)   # hungry by 19:00
        mult, reasons = trip_ctx.poi_multiplier(RESTAURANT, state, PROFILE)
        self.assertGreaterEqual(mult, 1.0)
        self.assertIn("toi, hop an uong/xa hoi", reasons)


class TestEdgeScorer(unittest.TestCase):
    def _ctx(self, satiety):
        return {"edge_state": {"satiety": satiety}}

    def test_still_full_adds_a_food_transition_penalty(self):
        base = soft_rules.edge_penalty(BEACH, RESTAURANT)
        full = soft_rules.edge_penalty(BEACH, RESTAURANT,
                                       self._ctx(0.9))
        self.assertEqual(base, 0.0)
        self.assertAlmostEqual(full, -soft_rules.EDGE_FOOD_FULL_PENALTY,
                               places=3)
        # Cafe only gets the light discount.
        cafe = soft_rules.edge_penalty(BEACH, CAFE, self._ctx(0.9))
        self.assertAlmostEqual(cafe, -soft_rules.EDGE_FOOD_FULL_CAFE_PENALTY,
                               places=3)

    def test_hungry_gets_a_meal_bonus(self):
        hungry = soft_rules.edge_penalty(BEACH, RESTAURANT, self._ctx(0.1))
        self.assertAlmostEqual(hungry, soft_rules.EDGE_FOOD_HUNGRY_BONUS,
                               places=3)

    def test_edge_scores_threads_the_context(self):
        by_id = {"r1": RESTAURANT, "b1": BEACH}
        dry = scorer.edge_scores(["r1", "b1"], by_id)
        full = scorer.edge_scores(["r1", "b1"], by_id,
                                  ctx=self._ctx(0.9))
        self.assertLess(full[("b1", "r1")], dry[("b1", "r1")])
        self.assertEqual(full[("r1", "b1")], dry[("r1", "b1")])


def _probes(hhmm: str) -> list[int]:
    """Both state probes of a 60-min fixture stop (start + 15 / + 45)."""
    h, m = hhmm.split(":")
    start = int(h) * 60 + int(m)
    return [start + 15, start + 45]


class TestOptimizerBands(unittest.TestCase):
    """The hard part: the state must change WHERE a stop lands."""

    TRIP = optimizer.StubTrip(start_min=7 * 60, end_min=21 * 60,
                              origin_id=None)
    TRAVEL = {(a, b): 10 for a in ("beach", "museum", "market")
              for b in ("beach", "museum", "market") if a != b}
    POIS = [
        optimizer.StubPOI("beach", visit_min=60, open_min=7 * 60,
                          close_min=20 * 60, score=5.0, category="beach"),
        optimizer.StubPOI("museum", visit_min=60, open_min=8 * 60,
                          close_min=18 * 60, score=4.5, category="museum"),
        optimizer.StubPOI("market", visit_min=60, open_min=8 * 60,
                          close_min=21 * 60, score=4.0, category="market"),
    ]

    def _run(self, bands, scores):
        out = optimizer.optimize(
            self.POIS, self.TRAVEL, self.TRIP, timeout_s=5, workers=1,
            state_bands=bands, state_score=scores)
        self.assertIsNotNone(out["itinerary"])
        return {a["poi_id"]: a["start"] for a in out["itinerary"]["activities"]}

    def test_state_moves_the_beach_out_of_the_dip(self):
        bands = [(7 * 60, 13 * 60 + 30), (13 * 60 + 30, 15 * 60),
                 (15 * 60, 21 * 60)]
        bad = {(pid, k): 1.0 for pid in ("beach", "museum", "market")
               for k in range(3)}
        bad[("beach", 1)] = 0.2  # the 13:30-15:00 dip
        starts = self._run(bands, bad)
        self.assertFalse(any(13 * 60 + 30 <= p < 15 * 60
                             for p in _probes(starts["beach"])), starts)

    def test_state_can_pull_the_beach_into_its_only_good_band(self):
        bands = [(7 * 60, 13 * 60 + 30), (13 * 60 + 30, 15 * 60),
                 (15 * 60, 21 * 60)]
        good = {(pid, k): 0.2 for pid in ("beach", "museum", "market")
                for k in range(3)}
        good[("beach", 1)] = 1.6  # only the dip is good for this beach
        starts = self._run(bands, good)
        # Both probes inside the dip: the model must centre the visit there.
        start_probe, end_probe = _probes(starts["beach"])
        self.assertTrue(13 * 60 + 30 <= start_probe
                        and end_probe < 15 * 60, starts)

    def test_no_state_terms_keeps_the_old_result(self):
        base = optimizer.optimize(self.POIS, self.TRAVEL, self.TRIP,
                                  timeout_s=5, workers=1)
        neutral = {(pid, k): 1.0 for pid in ("beach", "museum", "market")
                   for k in range(3)}
        same = optimizer.optimize(
            self.POIS, self.TRAVEL, self.TRIP, timeout_s=5, workers=1,
            state_bands=[(7 * 60, 21 * 60)], state_score=neutral)
        self.assertEqual(base["itinerary"]["total_score"],
                         same["itinerary"]["total_score"])


class TestStateWeightTuning(unittest.TestCase):
    """TASK-3: STATE_WEIGHT 0.25 -> 0.5 must change the ORDER, not just a score.

    Fixed example: a 13:30-15:00 horizon that fits exactly ONE 60-min stop.
    The beach (rating 5.0) is in the 13:00-15:00 dip AND the midday heat, the
    museum (3.7) is the light/indoor option. The state multipliers come from
    the real trip_ctx (not synthetic), so this pins the tuning knob end-to-end:
    at 0.25 the solver still picks the beach, at 0.5 it picks the museum.
    """

    TRIP_DICT = {"start_time": "13:30", "end_time": "15:00",
                 "budget": 1000000}
    TRIP = optimizer.StubTrip(start_min=13 * 60 + 30, end_min=15 * 60,
                              origin_id=None)
    POIS = [
        optimizer.StubPOI("beach", visit_min=60, open_min=7 * 60,
                          close_min=18 * 60, score=5.0, category="beach"),
        optimizer.StubPOI("museum", visit_min=60, open_min=8 * 60,
                          close_min=18 * 60, score=3.7, category="museum"),
    ]
    TRAVEL = {("beach", "museum"): 10, ("museum", "beach"): 10}

    def _bands(self):
        ctx = trip_ctx.build(self.TRIP_DICT,
                             {"party_type": "solo", "pace": 2},
                             fetch_weather=False)
        bands, scores = trip_ctx.optimizer_state(ctx, [
            {"poi_id": "beach", "cat": "beach", "weather_sensitive": True},
            {"poi_id": "museum", "cat": "museum"}])
        return bands, scores

    def _pick(self, weight):
        bands, scores = self._bands()
        out = optimizer.optimize(self.POIS, self.TRAVEL, self.TRIP,
                                 workers=1, timeout_s=5, state_bands=bands,
                                 state_score=scores, state_weight=weight)
        self.assertIsNotNone(out["itinerary"])
        acts = out["itinerary"]["activities"]
        self.assertEqual(len(acts), 1, acts)
        return acts[0]["poi_id"], out

    def test_multipliers_are_the_real_ones(self):
        _bands, scores = self._bands()
        # Beach in the dip + heat: 0.6 * 0.5; museum light/indoor: 1.1 * 1.15.
        self.assertAlmostEqual(scores[("beach", 0)], 0.3, places=3)
        self.assertAlmostEqual(scores[("museum", 0)], 1.265, places=3)

    def test_weight_flips_the_rank_order(self):
        old, _ = self._pick(0.25)
        new, _ = self._pick(optimizer.STATE_WEIGHT)
        self.assertEqual(old, "beach", "0.25 was too timid: it kept the dip")
        self.assertEqual(new, "museum",
                         "0.5 must move the stop out of the bad band")
        self.assertNotEqual(old, new)  # an ORDER change, not a score change

    def test_default_is_half(self):
        self.assertAlmostEqual(optimizer.STATE_WEIGHT, 0.5)

    def test_gates_stay_green_for_the_flipped_plan(self):
        from BE.app.services.gate import check_hcs, check_no_consecutive, \
            check_vroh
        bands, scores = self._bands()
        out = optimizer.optimize(self.POIS, self.TRAVEL, self.TRIP,
                                 workers=1, timeout_s=5, state_bands=bands,
                                 state_score=scores)
        itinerary = out["itinerary"]
        pois = {"beach": {"verified": True, "fee": 0,
                          "opening_hours": ["00:00-23:59"], "cat": "beach"},
                "museum": {"verified": True, "fee": 0,
                           "opening_hours": ["08:00-18:00"], "cat": "museum"}}
        trip = {"budget": 1000000, "start_time": "13:30", "end_time": "15:00"}
        self.assertTrue(check_vroh(itinerary, trip, pois, {})["passed"])
        self.assertTrue(check_no_consecutive(itinerary, trip, pois,
                                             {})["passed"])
        self.assertTrue(check_hcs(itinerary, trip, pois, {})["passed"])


if __name__ == "__main__":
    unittest.main()
