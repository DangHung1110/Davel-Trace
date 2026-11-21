"""Unit tests for BE/ml/data/v2_rules.py (danang-v2 labelling rules)."""

import os
import sys
import json
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

import v2_rules as R  # noqa: E402


class TestFoldAndMatch(unittest.TestCase):
    def test_fold_strips_diacritics(self):
        self.assertEqual(R.fold("Đỉnh Bàn Cờ"), "dinh ban co")

    def test_raw_keys_keep_diacritics_apart(self):
        # "đình" (communal house) vs "đỉnh" (peak) fold to the same word
        self.assertEqual(R.classify("Đình làng Hải Châu", None, None)[0], "religious")
        self.assertEqual(R.classify("Đỉnh Bàn Cờ", None, None)[0], "viewpoint")
        self.assertEqual(R.classify("Phở Hồng", "Nhà hàng", None)[0], "restaurant")


class TestClassify(unittest.TestCase):
    def test_business_type_beats_placeish_name(self):
        self.assertEqual(R.classify("Chill Beach Thanh Khê", "Nhà hàng hải sản", "restaurant")[0],
                         "restaurant")
        self.assertEqual(R.classify("A La Carte Danang Beach", "Khách sạn", "lodging")[0], "lodging")

    def test_specific_name_beats_type(self):
        self.assertEqual(R.classify("Jolie Cooking Class", "Lớp học nấu ăn", "attraction")[0],
                         "paid_attraction")
        self.assertEqual(R.classify("Chợ đêm Helio - B. Night Market", "Chợ đêm", "market")[0],
                         "night_market")
        self.assertEqual(R.classify("Chợ Miếu Bông", "Chợ", "market")[0], "day_market")

    def test_overrides_and_fallback(self):
        self.assertEqual(R.classify("Ngũ Hành Sơn", None, "attraction")[0], "paid_attraction")
        self.assertEqual(R.classify("xyz", None, "museum")[0], "museum_indoor")

    def test_exclusion_and_review(self):
        self.assertTrue(R.exclusion_reason("ANGEL LOUNGE", "Quán bar tiếp viên nữ"))
        self.assertIsNone(R.exclusion_reason("Nón Spa - Skin care", "Spa"))
        self.assertTrue(R.review_reason("Núi Hoi", "viewpoint", "osm:node/1"))
        self.assertIsNone(R.review_reason("Đỉnh Bàn Cờ", "viewpoint", "ChIJx"))

    def test_roles_cover_all_categories(self):
        self.assertEqual(set(R.ROLE_OF), set(R.ALL_CATEGORIES))
        self.assertEqual(R.ROLE_OF["lodging"], "base")


class TestZones(unittest.TestCase):
    def test_known_places(self):
        self.assertEqual(R.zone_of(16.0613, 108.2270), "trung_tam")         # Cầu Rồng
        self.assertEqual(R.zone_of(16.0617, 108.2470), "son_tra_my_khe")    # Mỹ Khê
        self.assertEqual(R.zone_of(16.0037, 108.2632), "ngu_hanh_son")      # Ngũ Hành Sơn
        self.assertEqual(R.zone_of(15.8801, 108.3380), "hoi_an")            # Hội An
        self.assertEqual(R.zone_of(15.9950, 107.9960), "ba_na_tay")         # Bà Nà
        self.assertEqual(R.zone_of(16.1920, 108.1310), "hai_van_lien_chieu")  # Hải Vân


class TestHours(unittest.TestCase):
    def test_intersection_of_day_variants(self):
        got = R.intersect_all(["10:00-22:30", "13:00-22:30"])
        self.assertEqual(R.fmt(got), ["13:00-22:30"])

    def test_split_and_overnight(self):
        got = R.intersect_all(["10:30-14:00, 16:30-22:30", "10:30-22:30"])
        self.assertEqual(R.fmt(got), ["10:30-14:00, 16:30-22:30"])
        bar = R.intersect_all(["17:00-02:00", "18:00-03:00"])
        self.assertEqual(R.fmt(bar), ["18:00-02:00"])

    def test_24h_and_empty(self):
        self.assertEqual(R.fmt(R.intersect_all(["00:00-23:59"])), ["00:00-23:59"])
        self.assertEqual(R.intersect_all([]), [])

    def test_disjoint_variants_give_empty(self):
        self.assertEqual(R.intersect_all(["05:00-05:30", "18:00-18:30"]), [])

    def test_osm_hours_subset(self):
        w = R.parse_osm_hours("Mo-Fr 08:00-17:00; Sa 08:00-12:00; Su off")
        self.assertEqual(w["Mo"], [(480, 1020)])
        self.assertEqual(w["Su"], [])
        self.assertEqual(R.week_intersection(w), [])
        self.assertEqual(R.week_intersection(R.parse_osm_hours("Mo-Su 10:30-22:00")), [(630, 1320)])
        self.assertIsNone(R.parse_osm_hours("sunrise-sunset"))

    def test_archetypes(self):
        self.assertEqual(R.archetype_of("restaurant", "Ốc Hút Cô Ba"), "an_toi")
        self.assertEqual(R.archetype_of("restaurant", "Bánh mì Bà Lan"), "an_sang")
        self.assertEqual(R.archetype_of("restaurant", "Mì Quảng Bà Vị"), "com_trua")
        self.assertEqual(R.archetype_of("day_market", "Chợ Hàn"), "cho_ngay")
        self.assertEqual(R.archetype_of("day_market", "Đặc sản Đà Nẵng làm quà"), "cua_hang")
        self.assertEqual(R.archetype_of("viewpoint", "Đỉnh Bàn Cờ"), "ngoai_troi_tu_nhien")
        for a in R.ARCHETYPES.values():
            for w in a["safe"]:
                self.assertTrue(R.parse_element(w))


class TestPrices(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(R.band_of(30_000), "re")
        self.assertEqual(R.band_of(100_000), "vua")
        self.assertEqual(R.band_of(400_000), "kha")
        self.assertEqual(R.band_of(450_000), "cao")
        self.assertEqual(R.legacy_band(300_000), "medium")

    def test_google_note(self):
        g = R.parse_google_price("~500.000đ (khoảng 200-800\xa0N\xa0₫)")
        self.assertEqual(g, {"typical": 500000, "min": 200000, "max": 800000})
        g = R.parse_google_price("~100.000đ (khoảng 1-200.000\xa0₫)")
        self.assertEqual(g["max"], 200000)
        self.assertIsNone(g["min"])

    def test_user_note(self):
        self.assertEqual(R.parse_user_price("user: Muối Biển 100-200k, món 450k+"),
                         {"min": 100000, "max": 200000})
        self.assertEqual(R.parse_user_price("user: Le Comptoir từ 400k"),
                         {"min": 400000, "max": None})
        self.assertEqual(R.parse_user_price("user: Xanh 150k-1200k, vote medium"),
                         {"min": 150000, "max": 1200000})


if __name__ == "__main__":
    unittest.main()
