"""Dish data (`tags.dishes`, 2026-11-24): vocabulary, build rules and matching.

A wish or food pref that names a dish ("muốn ăn bún chả cá") must find the shops
that serve it, and only those:
- the name rules read a dish off a shop name without false hits ("cơm cháy" is
  not vegetarian, "bún thịt nướng" is not a BBQ grill, "bún chả" is not "bún chả cá");
- `poi_view` exposes the dishes as `dishes` (names) and `cuisine` (every way to
  say them), the field the taste / allergy / gate haystacks already read;
- a dish phrase is a wish of its own: before 24/11 "ăn bánh tráng cuốn thịt heo"
  fitted every restaurant, because only the word "ăn" was understood;
- the build keeps one entry per dish, web (URL) over OSM over the name, and drops
  a web row without a URL.

Run: python -m pytest BE/tests/unit/test_dishes.py -q
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

from BE.common import (DISHES, dish_phrases, dishes_from_name,  # noqa: E402
                       dishes_from_osm_cuisine, poi_view)
from BE.app.services import profile_filter, retrieval  # noqa: E402
from migrate_v2 import build_dishes  # noqa: E402


def _v21(pid, name, dishes=(), category="restaurant"):
    """Minimal danang-v2.1 record (what poi_view reads)."""
    return {"poi_id": pid, "name": name, "category": category, "role": "meal",
            "status": "active", "data_version": "v2.1",
            "hours": {"open": ["06:00-22:00"], "kind": "fixed", "closed_days": [],
                      "access_window": None, "archetype": "nha_hang"},
            "price": {"tier": "cheap", "note": None}, "dwell": {"p25": 20, "p50": 30, "p75": 45},
            "tags": {"space": "indoor", "party": [], "good_times": [], "time_budget": [],
                     "effort": 1, "indoor": True, "kid_friendly": True, "weather_sensitive": False,
                     "dishes": [{"dish": d, "source": "web", "url": "https://example.org"}
                                for d in dishes]},
            "popularity": {"prize_prior": 0.45}, "provenance": {}, "ext_ids": {}}


BUN_CHA_CA = poi_view(_v21("bcc", "Quán Hờn", ["bun_cha_ca"]), policy="cach_ly")
PORK_ROLLS = poi_view(_v21("bth", "Quán Mậu", ["banh_trang_thit_heo"]), policy="cach_ly")
VEGAN = poi_view(_v21("veg", "Loving Vegan", ["mon_chay"]), policy="cach_ly")
PLAIN = poi_view(_v21("plain", "Nhà hàng Hai Cử"), policy="cach_ly")


class TestNameRules(unittest.TestCase):
    def test_dish_read_off_the_name(self):
        cases = {
            "Bún chả cá 109": ["bun_cha_ca"],
            "Quán Mậu - Bánh tráng thịt heo": ["banh_trang_thit_heo"],
            "Mỳ Quảng Bà Mua": ["mi_quang"],
            "Nhà hàng chay Hoa Sen": ["mon_chay"],
            "Phố Nướng Tokyo": ["do_nuong"],
            "ỐC HÀN - ĐÀ NẴNG": ["oc"],
            "Hải Sản Ốc 68": ["hai_san", "oc"],
            "Bún Mắm Vân": ["bun_mam"],
            "Bun cha ca 17k": ["bun_cha_ca"],          # OSM name without diacritics
        }
        for name, want in cases.items():
            self.assertEqual(dishes_from_name(name), want, name)

    def test_no_false_dish(self):
        self.assertEqual(dishes_from_name("Cơm cháy Cô Ba"), [])          # cháy is not chay
        self.assertEqual(dishes_from_name("Phố đi bộ Bạch Đằng"), [])      # phố is not phở
        self.assertEqual(dishes_from_name("Bún Thịt Nướng Bà Ngọc"), ["bun_thit_nuong"])
        self.assertEqual(dishes_from_name("Bún Chả Hà Nội"), ["bun_cha"])
        self.assertEqual(dishes_from_name("Bánh canh chả cá Tư"), ["banh_canh"])

    def test_osm_cuisine(self):
        self.assertEqual(dishes_from_osm_cuisine("vietnamese;seafood"), ["hai_san"])
        self.assertEqual(dishes_from_osm_cuisine("korean;barbecue"), ["do_nuong"])
        self.assertEqual(dishes_from_osm_cuisine("coffee_shop"), [])
        kitchen_sink = "burger;pizza;sushi;seafood;grill;pasta;noodles"
        self.assertEqual(dishes_from_osm_cuisine(kitchen_sink), [])

    def test_every_dish_has_a_name_and_phrases(self):
        for dish_id, d in DISHES.items():
            self.assertTrue(d["vi"] and d["aka"], dish_id)
            self.assertTrue(d.get("name") or d.get("name_vi"), dish_id)
            self.assertEqual(list(d["aka"]), [a.lower() for a in d["aka"]], dish_id)


class TestBuild(unittest.TestCase):
    def _rec(self, name, category="restaurant", osm="node/1"):
        return {"poi_id": "x", "name": name, "category": category, "ext_ids": {"osm": osm}}

    def test_web_over_osm_over_name_one_entry_per_dish(self):
        rows = [{"dishes": ["hai_san"], "evidence_url": "https://guide.example/sea", "_file": "f"}]
        out = build_dishes(self._rec("Hải Sản Ốc 68"), rows, "seafood")
        self.assertEqual(out, [
            {"dish": "hai_san", "source": "web", "url": "https://guide.example/sea"},
            {"dish": "oc", "source": "name", "url": None},
        ])

    def test_osm_entry_links_the_element(self):
        out = build_dishes(self._rec("Bé Ni 2", osm="node/12372814701"), [], "fish;seafood")
        self.assertEqual(out, [{"dish": "hai_san", "source": "osm",
                                "url": "https://www.openstreetmap.org/node/12372814701"}])

    def test_row_without_url_or_unknown_dish_is_dropped(self):
        rows = [{"dishes": ["bun_cha_ca"], "evidence_url": None, "_file": "f"},
                {"dishes": ["mon_la"], "evidence_url": "https://x.example", "_file": "f"}]
        self.assertEqual(build_dishes(self._rec("Quán Hờn"), rows), [])

    def test_only_food_places_carry_dishes(self):
        self.assertEqual(build_dishes(self._rec("Bãi biển Bánh Xèo", "beach"), []), [])
        self.assertEqual(build_dishes(self._rec("Chè Liên", "cafe"), []),
                         [{"dish": "che", "source": "name", "url": None}])


class TestView(unittest.TestCase):
    def test_view_exposes_dishes_and_cuisine(self):
        self.assertEqual(BUN_CHA_CA["dishes"], ["bún chả cá"])
        self.assertEqual(BUN_CHA_CA["cuisine"], ["bún chả cá", "chả cá"])
        self.assertNotIn("dishes", BUN_CHA_CA["smart_tags"])
        self.assertEqual(PLAIN["dishes"], [])
        self.assertEqual(dish_phrases(["mon_chay", "nope"])[:2], ["món chay", "đồ chay"])


class TestMatching(unittest.TestCase):
    def test_taste_reads_the_dish(self):
        for pref in ("bún chả cá", "bún", "chả cá", "local_cuisine"):
            self.assertGreater(profile_filter.taste_score(BUN_CHA_CA, [pref])[0], 0, pref)
            self.assertEqual(profile_filter.taste_score(PLAIN, [pref])[0], 0, pref)
        for pref in ("bánh tráng thịt heo", "bánh tráng cuốn thịt heo", "bánh tráng"):
            self.assertGreater(profile_filter.taste_score(PORK_ROLLS, [pref])[0], 0, pref)
        for pref in ("đồ chay", "ăn chay", "vegetarian_option"):
            self.assertGreater(profile_filter.taste_score(VEGAN, [pref])[0], 0, pref)

    def test_vegan_kitchen_clashes_with_a_grill_wish(self):
        unit, _hits, clashes = profile_filter.taste_score(VEGAN, ["đồ nướng"])
        self.assertEqual(unit, -profile_filter.TASTE_MISMATCH)
        self.assertEqual(clashes, ["vegan"])

    def test_dish_wish_narrows_to_the_shops_that_serve_it(self):
        self.assertTrue(retrieval.poi_fits_wish(BUN_CHA_CA, "ăn bún chả cá"))
        self.assertFalse(retrieval.poi_fits_wish(PLAIN, "ăn bún chả cá"))
        self.assertTrue(retrieval.poi_fits_wish(PORK_ROLLS, "ăn bánh tráng cuốn thịt heo"))
        self.assertTrue(retrieval.poi_fits_wish(PORK_ROLLS, "bánh tráng thịt heo"))
        self.assertFalse(retrieval.poi_fits_wish(PLAIN, "ăn bánh tráng cuốn thịt heo"))
        self.assertFalse(retrieval.poi_fits_wish(PLAIN, "ăn ốc"))
        self.assertTrue(retrieval.poi_fits_wish(VEGAN, "đồ chay"))

    def test_food_wish_as_activity_keeps_the_dish(self):
        # the whole dish, not its "cá": any fish kitchen would score the same
        self.assertEqual(profile_filter.cuisine_terms("ăn bún chả cá"), ["bún chả cá"])
        self.assertEqual(profile_filter.cuisine_terms("ăn hải sản"), ["hải sản"])
        self.assertEqual(profile_filter.cuisine_terms("đi dạo biển"), [])
        self.assertEqual(profile_filter.cuisine_terms("chạy bộ ven sông"), [])   # chạy is not chay
        self.assertEqual(profile_filter.cuisine_terms("an chay")[:1], ["ăn chay"])  # typed bare

    def test_allergy_sees_the_dish(self):
        self.assertIsNotNone(profile_filter.drop_reason(BUN_CHA_CA, {"allergy": ["fish"]}))
        self.assertIsNotNone(profile_filter.drop_reason(PORK_ROLLS, {"allergy": ["pork"]}))
        self.assertIsNone(profile_filter.drop_reason(PLAIN, {"allergy": ["fish"]}))


if __name__ == "__main__":
    unittest.main()
