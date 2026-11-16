"""The onboarding's SOFT answers reach the plan, not only the rank list.

The page (FE/onboard.html) calls `spending_level`, `outdoor_bias`, `activities` and
`food_prefs` "SOFT — trọng số điểm". Three of them fed only the ranker, which orders
candidates and explains them; the fourth sent catalog codes ("seafood") the Vietnamese
snapshot never matched. Whatever was answered, the day came out the same: on 12 real
days the restaurants had the same price level at spending 1, 2 and 3 in 10.

Pinned here:
- a neutral profile (level 2, bias 0, nothing ticked) leans nowhere, so it plans as before;
- spending leans to the places that cost what the level asks, read against what such a
  place usually costs (a cheap restaurant, not "cheaper than a park");
- outdoor_bias leans on what the ranker already called outdoor (one definition);
- a liked activity is the wish it stands for, read by the wish matcher, as a lean
  (never a required stop);
- catalog food codes find the words the data uses, and "has a vegetarian choice" never
  makes a cuisine clash;
- the lean wins the slot in a real plan and is named in the stop's evidence.

Run: python -m pytest BE/tests/unit/test_profile_leaning.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import profile_filter, profiles, rank, retrieval, soft_rules, trip_ctx  # noqa: E402
from BE.app.services.profiles import (  # noqa: E402
    LIKED_WEIGHT, OUTDOOR_WEIGHT, SPENDING_WEIGHT, build_plan, price_reference, soft_lean)

NEUTRAL = {"party_type": "solo", "pace": 2, "fitness": 2, "spending_level": 2,
           "outdoor_bias": 0.0, "activities": [], "food_prefs": []}


def poi(pid, cat, **extra):
    base = {"poi_id": pid, "name": pid, "cat": cat, "type": cat, "tags": [cat], "rating": 4.5,
            "fee": 0, "intensity": 1, "opening_hours": ["08:00-22:00"], "visit_min": 60,
            "verified": True}
    base.update(extra)
    return base


CHEAP = poi("cheap", "restaurant", price_level=1)
MID = poi("mid", "restaurant", price_level=2)
DEAR = poi("dear", "restaurant", price_level=3)
CAFE = poi("cafe", "cafe", price_level=1)
BEACH = poi("beach", "beach", weather_sensitive=True)
MUSEUM = poi("museum", "museum", name="Bảo tàng Chăm", type="Bảo tàng", tags=["Bảo tàng"])
PAGODA = poi("pagoda", "temple", name="Chùa Linh Ứng", type="Chùa", tags=["Chùa Phật giáo"])
CHURCH = poi("church", "temple", name="Nhà thờ Con Gà", type="Nhà thờ", tags=["Nhà thờ Công giáo"])
TERRACE = poi("terrace", "restaurant", price_level=2, weather_sensitive=True)
REF = {"restaurant": 2, "cafe": 1}


class TestLikedActivities(unittest.TestCase):
    def test_a_catalog_code_is_the_wish_it_stands_for(self):
        self.assertEqual(retrieval.liked_wishes(["beach", "museum", "nightlife"]),
                         ["tắm biển", "bảo tàng", "quán bar"])

    def test_other_text_is_read_as_typed_and_nothing_twice(self):
        self.assertEqual(retrieval.liked_wishes(["tắm biển", "beach", "Beach", "", None]), ["tắm biển"])

    def test_a_code_with_no_place_in_the_data_likes_nothing(self):
        self.assertEqual(retrieval.liked_wishes(["golf"]), [])

    def test_every_catalog_code_is_a_wish_the_matcher_understands(self):
        for code, wish in retrieval.CATALOG_ACTIVITY_WISH.items():
            if wish:
                self.assertTrue(retrieval.match_activity(wish), code)

    def test_the_wish_matcher_decides_what_is_liked(self):
        self.assertTrue(retrieval.poi_is_liked(BEACH, retrieval.liked_wishes(["beach"])))
        self.assertTrue(retrieval.poi_is_liked(MUSEUM, retrieval.liked_wishes(["museum"])))
        temple = retrieval.liked_wishes(["temple"])          # "tâm linh": pagodas, not churches
        self.assertTrue(retrieval.poi_is_liked(PAGODA, temple))
        self.assertFalse(retrieval.poi_is_liked(CHURCH, temple))
        self.assertFalse(retrieval.poi_is_liked(MUSEUM, retrieval.liked_wishes(["beach"])))


class TestSoftLean(unittest.TestCase):
    def test_a_neutral_profile_leans_nowhere(self):
        for place in (CHEAP, MID, DEAR, CAFE, BEACH, MUSEUM, TERRACE):
            self.assertEqual(soft_lean(place, NEUTRAL, [], REF), (0.0, []), place["poi_id"])
        self.assertEqual(soft_lean(BEACH, None), (0.0, []))
        self.assertEqual(soft_lean(BEACH, {}), (0.0, []))

    def test_thrifty_leans_to_the_cheap_table_and_premium_to_the_dear_one(self):
        thrifty, premium = {**NEUTRAL, "spending_level": 1}, {**NEUTRAL, "spending_level": 3}
        self.assertEqual([soft_lean(p, thrifty, [], REF)[0] for p in (CHEAP, MID, DEAR)],
                         [SPENDING_WEIGHT, 0.0, -SPENDING_WEIGHT])
        self.assertEqual([soft_lean(p, premium, [], REF)[0] for p in (CHEAP, MID, DEAR)],
                         [-SPENDING_WEIGHT, 0.0, SPENDING_WEIGHT])
        self.assertEqual(soft_lean(CHEAP, thrifty, [], REF)[1], ["hop muc chi tieu"])
        self.assertEqual(soft_lean(DEAR, thrifty, [], REF)[1], [])       # a lean against is no evidence

    def test_cheap_means_cheap_for_such_a_place(self):
        # Nearly every cafe is level 1: that is what a cafe costs, not a bargain, and a
        # free beach is not "cheaper" than a restaurant.
        thrifty = {**NEUTRAL, "spending_level": 1}
        self.assertEqual(soft_lean(CAFE, thrifty, [], REF)[0], 0.0)
        self.assertEqual(soft_lean(BEACH, thrifty, [], REF)[0], 0.0)
        self.assertEqual(soft_lean(poi("nice", "cafe", price_level=2), thrifty, [], REF)[0],
                         -SPENDING_WEIGHT)

    def test_price_reference_is_the_usual_level_of_each_priced_category(self):
        pool = [CHEAP, MID, MID, DEAR, CAFE, CAFE, poi("c2", "cafe", price_level=2), BEACH,
                poi("unknown", "restaurant", price_level=None)]
        self.assertEqual(price_reference(pool), {"restaurant": 2, "cafe": 1})

    def test_outdoor_bias_moves_what_the_ranker_calls_outdoor(self):
        out, indoors = {**NEUTRAL, "outdoor_bias": 1.0}, {**NEUTRAL, "outdoor_bias": -0.5}
        self.assertEqual(soft_lean(BEACH, out, [], REF), (OUTDOOR_WEIGHT, ["hop gu ngoai troi"]))
        self.assertEqual(soft_lean(TERRACE, out, [], REF)[0], OUTDOOR_WEIGHT)
        self.assertEqual(soft_lean(MUSEUM, out, [], REF), (0.0, []))
        self.assertEqual(soft_lean(BEACH, indoors, [], REF), (round(-0.5 * OUTDOOR_WEIGHT, 4), []))
        # One definition for the ranker, the traveller state and the solver.
        self.assertTrue(soft_rules.is_outdoor(BEACH) and soft_rules.is_outdoor(TERRACE))
        self.assertFalse(soft_rules.is_outdoor(MUSEUM))
        self.assertIs(trip_ctx.OUTDOOR_CATEGORIES, soft_rules.OUTDOOR_CATEGORIES)
        reasons = rank.score_poi(BEACH, {"outdoor_bias": 1.0}, {"hour": "09:00"})["reasons"]
        self.assertIn("hop gu ngoai troi", reasons)

    def test_a_liked_activity_is_a_lean_with_its_reason(self):
        liked = retrieval.liked_wishes(["beach", "museum"])
        self.assertEqual(soft_lean(BEACH, NEUTRAL, liked, REF), (LIKED_WEIGHT, ["hop hoat dong ban thich"]))
        self.assertEqual(soft_lean(MUSEUM, NEUTRAL, liked, REF)[0], LIKED_WEIGHT)
        self.assertEqual(soft_lean(PAGODA, NEUTRAL, liked, REF), (0.0, []))

    def test_the_leans_add_up(self):
        card = {**NEUTRAL, "outdoor_bias": -0.5}                 # the family card: likes the beach, leans indoors
        lean, reasons = soft_lean(BEACH, card, retrieval.liked_wishes(["beach"]), REF)
        self.assertAlmostEqual(lean, LIKED_WEIGHT - 0.5 * OUTDOOR_WEIGHT)
        self.assertEqual(reasons, ["hop hoat dong ban thich"])

    def test_the_weights_are_leans_not_a_second_score(self):
        for weight in (SPENDING_WEIGHT, OUTDOOR_WEIGHT, LIKED_WEIGHT):
            self.assertTrue(0.05 <= weight <= profiles.TASTE_WEIGHT)


class TestCatalogFoodPrefs(unittest.TestCase):
    SEAFOOD = poi("sea", "restaurant", name="Hải sản Bé Mặn", type="Nhà hàng hải sản", tags=["Nhà hàng hải sản"])
    GRILL = poi("grill", "restaurant", name="Quán nướng Ba Con Dê", type="Nhà hàng", tags=["Nhà hàng món nướng"])
    NOODLE = poi("noodle", "restaurant", name="Mì Quảng Bà Mua", type="Quán mì", tags=["Quán mì"])
    VEGAN = poi("vegan", "restaurant", name="Nhà hàng chay Hoa Sen", type="Nhà hàng", tags=["Nhà hàng ăn chay"])
    FAMILY = poi("family", "restaurant", name="Cơm nhà", type="Nhà hàng", tags=["Nhà hàng gia đình"],
                 smart_tags={"party": ["family", "couple", "group"]})
    PLAIN = poi("plain", "restaurant", name="Madame Lân", type="Nhà hàng", tags=["Nhà hàng"],
                smart_tags={"party": ["family", "couple", "group"]})

    def unit(self, place, *prefs):
        return profile_filter.taste_score(place, list(prefs))[0]

    def test_a_code_finds_the_words_the_snapshot_uses(self):
        self.assertEqual(self.unit(self.SEAFOOD, "seafood"), 1.0)
        self.assertEqual(self.unit(self.GRILL, "BBQ"), 1.0)
        self.assertEqual(self.unit(self.NOODLE, "local_cuisine"), 1.0)
        self.assertEqual(self.unit(self.NOODLE, "street_food"), 1.0)
        self.assertEqual(self.unit(self.VEGAN, "vegan_only"), 1.0)
        self.assertEqual(self.unit(self.PLAIN, "seafood"), 0.0)

    def test_several_ticked_codes_share_the_bonus(self):
        self.assertEqual(self.unit(self.SEAFOOD, "seafood", "street_food", "BBQ", "beer"), 0.25)

    def test_typed_text_still_matches_as_itself(self):
        self.assertEqual(self.unit(self.SEAFOOD, "hải sản"), 1.0)
        self.assertEqual(self.unit(self.NOODLE, "mì quảng"), 1.0)

    def test_kid_friendly_is_a_family_restaurant_not_every_restaurant(self):
        # Every restaurant carries smart_tags.party = family: that must not be the hit.
        self.assertEqual(self.unit(self.FAMILY, "kid_friendly"), 1.0)
        self.assertEqual(self.unit(self.PLAIN, "kid_friendly"), 0.0)

    def test_vegan_only_clashes_with_a_grill_and_a_vegetarian_choice_does_not(self):
        unit, _hits, clashes = profile_filter.taste_score(self.GRILL, ["vegan_only"])
        self.assertEqual((unit, clashes), (-1.0, ["bbq"]))
        unit, _hits, clashes = profile_filter.taste_score(self.GRILL, ["vegetarian_option"])
        self.assertEqual((unit, clashes), (0.0, []))
        self.assertEqual(self.unit(self.VEGAN, "vegetarian_option"), 1.0)

    def test_every_catalog_code_has_its_words(self):
        codes = ("vietnamese", "seafood", "street_food", "local_cuisine", "cafe", "fine_dining",
                 "vegetarian_option", "vegan_only", "halal", "kid_friendly", "BBQ", "beer", "dessert")
        for code in codes:
            self.assertIn(profile_filter.fold(code), profile_filter.FOOD_PREF_GROUPS, code)
            self.assertEqual(profile_filter.food_pref_terms(code),
                             profile_filter.FOOD_PREF_GROUPS[profile_filter.fold(code)])


class TestTheLeanWinsTheSlot(unittest.TestCase):
    """A better-rated mid-priced kitchen takes lunch, unless the traveller is thrifty."""

    EATERY = poi("eatery", "restaurant", price_level=1, rating=4.4, opening_hours=["10:00-22:00"])
    BISTRO = poi("bistro", "restaurant", price_level=2, rating=4.7, opening_hours=["10:00-22:00"])
    OTHERS = [poi("dear2", "restaurant", price_level=3, rating=4.0, opening_hours=["17:00-22:00"]),
              poi("cafe1", "cafe", price_level=1, visit_min=45, opening_hours=["06:30-22:00"]),
              poi("mus1", "museum", name="Bảo tàng", type="Bảo tàng", tags=["Bảo tàng"],
                  opening_hours=["08:00-17:00"]),
              poi("beach1", "beach", name="Bãi biển", weather_sensitive=True, rating=4.4,
                  opening_hours=["00:00-23:59"], visit_min=90)]

    def plan(self, **profile):
        pois = [self.EATERY, self.BISTRO, *self.OTHERS]
        by_id = {p["poi_id"]: p for p in pois}
        cells = {f"{a}->{b}": {"minutes": 10, "km": 1.0} for a in by_id for b in by_id if a != b}
        trip = {"trip_id": "t", "budget": 3_000_000, "start_time": "08:00", "end_time": "16:00",
                "must_visit": [], "avoid": [], "food_prefs": [], "activities": [],
                "profile": {**NEUTRAL, **profile}}
        plan = build_plan("balanced", trip, [{"poi_id": pid} for pid in by_id], by_id, cells, template="")
        self.assertTrue(plan["passed"], plan.get("violations"))
        return plan

    def lunch(self, plan):
        for act in sorted(plan["activities"], key=lambda a: a["start"]):
            if act["poi_id"] in ("eatery", "bistro", "dear2") and "11:00" <= act["start"] < "13:00":
                return act
        return None

    def test_neutral_takes_the_better_rated_kitchen(self):
        self.assertEqual(self.lunch(self.plan())["poi_id"], "bistro")

    def test_a_thrifty_traveller_gets_the_eatery_and_is_told_why(self):
        lunch = self.lunch(self.plan(spending_level=1))
        self.assertEqual(lunch["poi_id"], "eatery")
        self.assertIn("hop muc chi tieu", lunch["explanation"]["evidence"])

    def test_a_liked_activity_is_in_the_evidence_of_its_stop(self):
        plan = self.plan(activities=["beach"])
        beach = next(a for a in plan["activities"] if a["poi_id"] == "beach1")
        self.assertIn("hop hoat dong ban thich", beach["explanation"]["evidence"])
        museum = next((a for a in plan["activities"] if a["poi_id"] == "mus1"), None)
        if museum is not None:
            self.assertNotIn("hop hoat dong ban thich", museum["explanation"]["evidence"])


if __name__ == "__main__":
    unittest.main()
