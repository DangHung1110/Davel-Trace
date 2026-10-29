"""TASK-2: taste scoring with teeth (rank component + optimizer unit).

The requirement, pinned here:
- a 4.5 seafood place MUST outrank a 4.9 BBQ joint for a seafood profile
  (a ~0.4 rating gap), both in the ranker AND in the optimizer's slot choice;
- an exclusive cuisine clash (vegan-only kitchen for a BBQ/seafood eater) is a
  SOFT penalty, never a drop (allergy/must_avoid own the hard exclusions);
- the rank weights still sum to 1 and the taste component is its own term.

Numbers (tuning record):
- rank: a 0.4 rating gap costs 0.4/5 * 0.22 = 0.0176; a full taste hit is
  0.18 * (1.0 - 0.5) = 0.09, i.e. ~5x the gap.
- optimizer: TASTE_WEIGHT * unit = 0.20 * 4.9 = 0.98 rating points vs the 0.4
  gap (0.098 vs 0.04 for the savings score scale).

Run: python -m pytest BE/tests/unit/test_taste_scoring.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import profile_filter, rank  # noqa: E402
from BE.app.services.profiles import TASTE_WEIGHT, build_plan  # noqa: E402

H = 60


def _rest(pid, rating, tags, name=None, hours=("10:00-22:00",), visit=60):
    return {"poi_id": pid, "name": name or pid, "cat": "restaurant",
            "type": "Nhà hàng", "tags": list(tags), "rating": rating,
            "fee": 0, "intensity": 1, "opening_hours": list(hours),
            "visit_min": visit, "verified": True}


SEAFOOD = _rest("sea", 4.5, ["Nhà hàng hải sản"], "Hải sản Biển Xanh")
BBQ = _rest("bbq", 4.9, ["Nhà hàng nướng BBQ"], "BBQ House")
VEGAN = _rest("vegan", 4.9, ["Nhà hàng chay"], "Nhà hàng chay Shanti Vegan")
PLAIN = _rest("plain", 4.4, ["Nhà hàng Việt Nam"], "Nhà hàng Việt")
SEAFOOD_PROFILE = {"food_prefs": ["hải sản"]}
BBQ_PROFILE = {"food_prefs": ["bbq", "thịt nướng"]}

CTX = {"hour": "12:00"}


class TestTasteUnit(unittest.TestCase):
    def test_full_hit_is_plus_one_and_neutral_is_zero(self):
        self.assertAlmostEqual(profile_filter.taste_score(SEAFOOD,
                                                         ["hải sản"])[0], 1.0)
        self.assertAlmostEqual(profile_filter.taste_score(PLAIN,
                                                         ["hải sản"])[0], 0.0)

    def test_partial_hit_sits_between(self):
        unit, _hits, _clashes = profile_filter.taste_score(
            SEAFOOD, ["hải sản", "chay"])
        self.assertGreater(unit, 0.0)
        self.assertLess(unit, 1.0)

    def test_vegan_kitchen_clashes_with_a_bbq_lover(self):
        unit, _hits, clashes = profile_filter.taste_score(VEGAN, ["bbq"])
        self.assertAlmostEqual(unit, -1.0)
        self.assertEqual(clashes, ["vegan"])

    def test_vegan_pref_does_not_clash_with_a_vegan_kitchen(self):
        unit, _hits, clashes = profile_filter.taste_score(VEGAN, ["chay"])
        self.assertGreater(unit, 0.0)
        self.assertEqual(clashes, [])

    def test_seafood_is_not_a_conflict_for_a_vietnamese_kitchen(self):
        unit, _hits, clashes = profile_filter.taste_score(PLAIN, ["hải sản"])
        self.assertEqual((unit, clashes), (0.0, []))

    def test_non_food_poi_is_neutral(self):
        beach = {"poi_id": "b", "cat": "beach", "tags": ["biển"]}
        self.assertEqual(profile_filter.taste_score(beach, ["hải sản"])[:2],
                         (0.0, []))


class TestRankTaste(unittest.TestCase):
    def test_weights_keep_summing_to_one(self):
        self.assertAlmostEqual(sum(rank.WEIGHTS.values()), 1.0)
        self.assertIn("taste", rank.WEIGHTS)

    def test_45_seafood_outranks_49_bbq_for_a_seafood_profile(self):
        ordered = rank.rank([BBQ, SEAFOOD], SEAFOOD_PROFILE, CTX)
        self.assertEqual(ordered[0]["poi_id"], "sea")
        gap = ordered[0]["score"] - ordered[1]["score"]
        self.assertGreater(gap, 0.0)
        # Beats the rating gap, not just ties it.
        rating_only_gap = (4.9 - 4.5) / 5.0 * rank.WEIGHTS["rating"]
        self.assertGreater(gap, rating_only_gap)

    def test_bbq_lover_keeps_the_bbq_place(self):
        ordered = rank.rank([BBQ, SEAFOOD], BBQ_PROFILE, CTX)
        self.assertEqual(ordered[0]["poi_id"], "bbq")

    def test_vegan_clash_costs_the_rank(self):
        ordered = rank.rank([VEGAN, SEAFOOD], SEAFOOD_PROFILE, CTX)
        self.assertEqual(ordered[0]["poi_id"], "sea",
                         "a 4.9 vegan-only kitchen must lose to a 4.5 seafood "
                         "place for a seafood profile")

    def test_no_prefs_keeps_the_rating_order(self):
        ordered = rank.rank([BBQ, SEAFOOD], {}, CTX)
        self.assertEqual(ordered[0]["poi_id"], "bbq")


class TestOptimizerTaste(unittest.TestCase):
    """The part rank alone cannot do: taste wins the SLOT."""

    @staticmethod
    def _trip(food_prefs):
        return {"trip_id": "t", "budget": 3000000, "start_time": "08:00",
                "end_time": "16:00", "must_visit": [], "avoid": [],
                "food_prefs": [], "activities": [],
                "profile": {"party_type": "solo", "pace": 2, "fitness": 2,
                            "food_prefs": list(food_prefs)}}

    @staticmethod
    def _pool(restaurants):
        pois = list(restaurants) + [
            {"poi_id": "cafe1", "name": "Cafe 1", "cat": "cafe",
             "type": "Quán cà phê", "tags": ["Quán cà phê"], "rating": 4.6,
             "fee": 0, "intensity": 1, "opening_hours": ["06:30-22:00"],
             "visit_min": 45, "verified": True},
            {"poi_id": "mus1", "name": "Bảo tàng", "cat": "museum",
             "type": "Bảo tàng", "tags": ["Bảo tàng"], "rating": 4.4,
             "fee": 0, "intensity": 1, "opening_hours": ["08:00-17:00"],
             "visit_min": 60, "verified": True},
        ]
        by_id = {p["poi_id"]: p for p in pois}
        cells = {f"{a}->{b}": {"minutes": 10, "km": 1.0}
                 for a in by_id for b in by_id if a != b}
        ranked = [{"poi_id": pid} for pid in by_id]
        return by_id, cells, ranked

    def _lunch(self, plan, by_id):
        """The one restaurant that starts inside the 11:00-13:00 lunch."""
        for act in sorted(plan["activities"], key=lambda a: a["start"]):
            poi = by_id[act["poi_id"]]
            if poi["cat"] != "restaurant":
                continue
            h, m = act["start"].split(":")
            if 11 * 60 <= int(h) * 60 + int(m) < 13 * 60:
                return act["poi_id"]
        return None

    def test_taste_weight_beats_a_04_rating_gap(self):
        """0.20 * 4.9 = 0.98 rating points at the balanced scale."""
        self.assertGreater(TASTE_WEIGHT * 4.9, 0.4)
        # ... and at the savings scale (rating * 0.1 -> unit 0.49).
        self.assertGreater(TASTE_WEIGHT * 0.49, 0.04)
        self.assertLess(TASTE_WEIGHT, 0.5)  # a unit knob, not a second rating

    def test_45_seafood_beats_49_bbq_in_the_slot_choice(self):
        by_id, cells, ranked = self._pool([BBQ, SEAFOOD])
        plan = build_plan("balanced", self._trip(["hải sản"]), ranked, by_id,
                          cells, template="")
        self.assertEqual(self._lunch(plan, by_id), "sea", [
            (a["start"], a["poi_id"]) for a in plan["activities"]])
        self.assertTrue(plan["passed"])

    def test_savings_scale_also_prefers_the_taste_hit(self):
        by_id, cells, ranked = self._pool([BBQ, SEAFOOD])
        plan = build_plan("savings", self._trip(["hải sản"]), ranked, by_id,
                          cells, template="")
        self.assertEqual(self._lunch(plan, by_id), "sea")

    def test_vegan_only_kitchen_loses_to_a_seafood_place(self):
        by_id, cells, ranked = self._pool([VEGAN, SEAFOOD])
        plan = build_plan("balanced", self._trip(["hải sản"]), ranked, by_id,
                          cells, template="")
        self.assertEqual(self._lunch(plan, by_id), "sea")

    def test_no_prefs_falls_back_to_rating(self):
        by_id, cells, ranked = self._pool([BBQ, SEAFOOD])
        plan = build_plan("balanced", self._trip([]), ranked, by_id, cells,
                          template="")
        self.assertEqual(self._lunch(plan, by_id), "bbq")


if __name__ == "__main__":
    unittest.main()
