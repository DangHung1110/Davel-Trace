"""Unit test for the Google-vs-OSM coordinate check (P0 data, BE/tools/coord_check_osm.py).

No osmium, no network: the name rules are tested on the examples the script
documents, and check_poi runs on a tiny synthetic OSM export.

Run from repo root: python BE/tests/unit/test_coord_check_osm.py -v
"""

import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.tools import coord_check_osm as cc  # noqa: E402


def lenient(a: str, b: str) -> tuple:
    return cc.name_level(cc.variants(cc.name_texts([a])), cc.variants(cc.name_texts([b])))


def strict(a: str, b: str, location=frozenset()) -> tuple:
    return cc.strict_level([cc.strict_form(t, location) for t in cc.name_texts([a])],
                           [cc.strict_form(t, location) for t in cc.name_texts([b])])


class NameRules(unittest.TestCase):
    def test_lenient_confirms_same_place_spellings(self):
        for a, b in [("Cộng Cà Phê", "Cộng Cà Phê"), ("le vénin spa", "Levenin Spa"),
                     ("Hải Sản Đà Nẵng Bé Biển", "Bé Bien"), ("Àla Cafe Roaster", "Àla Cafe"),
                     ("F29 Golden Beef & Sky Bar", "F29"), ("Mì Quảng Thi", "Mi Quang Thi 251"),
                     ("Oani Spa", "Aoni Spa"),
                     ("Bảo tàng 3D Art In Paradise", "Art in Paradise Da Nang 3D Museum")]:
            level, weak = lenient(a, b)
            self.assertGreater(level, 0, (a, b))
            self.assertFalse(weak, (a, b))

    def test_lenient_rejects_kind_words_and_reversed_places(self):
        for a, b in [("Bảo tàng Đà Nẵng", "Bảo tàng Mỹ thuật Đà Nẵng"),
                     ("Nhà hàng hải sản", "Nhà Hàng Hải Sản Bé Mặn"),
                     ("Mì Quảng Bà Vị", "My Quang Bà Mua"),
                     ("Siêu thị Đặc sản Hương Đà", "Siêu thị Co.op"),
                     ("Lee Spa", "Lá sen Spa")]:
            self.assertEqual(lenient(a, b)[0], 0, (a, b))
        level, weak = lenient("Phố đi bộ phố cổ Hội An", "Vườn Tượng An Hội")
        self.assertTrue(level == 0 or weak)

    def test_place_names_only_are_weak(self):
        self.assertEqual(lenient("Nhà thờ Giáo xứ An Hòa", "Nhà thờ An Hòa"), (cc.PARTIAL, True))

    def test_strict_needs_matching_tone_marks(self):
        self.assertEqual(strict("Nhà Thờ Giáo Xứ Phước Tường", "Nhà thờ Giáo xứ Phước Tượng")[0], 0)
        self.assertEqual(cc.accent_key("hoà"), cc.accent_key("hòa"))
        self.assertGreater(strict("Nhà thờ Phú Thượng", "nhà thờ Phú Thượng")[0], 0)
        # a name typed without marks still matches
        self.assertGreater(strict("Hải sản My Hạnh", "Hai San My Hanh")[0], 0)

    def test_strict_drops_streets_and_wards(self):
        location = {"lien chieu", "dien bien phu"}
        self.assertEqual(strict("PHỐ NƯỚNG ( Trần Triệu Luật - Liên Chiểu)", "PNJ Liên Chiểu",
                                location)[0], 0)
        self.assertEqual(strict("Sushi Time - 305 Điện Biên Phủ", "YODY Điện Biên Phủ",
                                location)[0], 0)

    def test_far_accusation_needs_two_equal_words(self):
        level, shared = strict("New World Spa", "New World Hoiana Hotel")
        self.assertFalse(cc.accusable(level, shared, "match", [("new",), ("world",)], far=True))
        level, shared = strict("Gyu Sachi", "Gyu Sachi")
        self.assertTrue(cc.accusable(level, shared, "match", [("gyu",), ("sachi",)], far=True))

    def test_helpers(self):
        self.assertTrue(cc._one_edit("oanispa", "aonispa"))
        self.assertFalse(cc._one_edit("abc", "xyz"))
        self.assertEqual(cc.osm_ref("n12"), "node/12")
        self.assertEqual(cc.osm_ref("a68"), "way/34")
        self.assertEqual(cc.osm_ref("a69"), "relation/34")
        self.assertEqual(cc.ref_of_ext("way/34"), {"w34", "a68"})
        streets = {"ong ich duong": [], "dung si thanh khe": []}
        self.assertEqual(cc.street_in_name(
            {"name": "Quán Mỳ Quảng Bà Mua - 58 Ông Ích Đường"}, streets), ("ong ich duong", "number"))
        # "07 Dũng sĩ" are seven heroes, not a house number
        self.assertEqual(cc.street_in_name(
            {"name": "Nhà Lưu niệm Mẹ Nhu và 07 Dũng sĩ Thanh Khê"}, streets), (None, None))


def feature(fid, tags, geometry):
    return {"type": "Feature", "id": fid, "properties": tags, "geometry": geometry}


def point(lat, lon):
    return {"type": "Point", "coordinates": [lon, lat]}


def poi(pid, name, category, lat, lon, role="meal", note=None):
    prov = {"location": {"source": "google_maps"}}
    if note:
        prov["price"] = {"note": note}
    return {"poi_id": pid, "name": name, "name_raw": name, "name_en": None, "category": category,
            "role": role, "zone": "trung_tam", "status": "active", "lat": lat, "lon": lon,
            "ext_ids": {"osm": None, "google_place_id": pid}, "provenance": prov}


class CheckPoi(unittest.TestCase):
    """Synthetic town around (16.06, 108.22); 0.001 deg lat ~ 110 m."""

    @classmethod
    def setUpClass(cls):
        lat0, lon0 = 16.06, 108.22
        cls.lat0, cls.lon0 = lat0, lon0
        named = [
            feature("n1", {"name": "Bé Bien", "amenity": "restaurant"}, point(lat0 + 0.0001, lon0)),
            feature("n2", {"name": "nhà thờ Phú Thượng", "amenity": "place_of_worship"},
                    point(lat0 - 0.0047, lon0)),
            feature("n3", {"name": "Gyu Sachi", "amenity": "restaurant"},
                    point(lat0 - 0.03, lon0 + 0.02)),
            feature("w1", {"name": "Quang Trung", "highway": "secondary"},
                    {"type": "LineString", "coordinates": [[lon0 - 0.01, lat0 + 0.0100],
                                                           [lon0 + 0.01, lat0 + 0.0100]]}),
        ]
        roads = [feature("w1", {"highway": "secondary"},
                         {"type": "LineString", "coordinates": [[lon0 - 0.01, lat0 + 0.0001],
                                                                [lon0 + 0.01, lat0 + 0.0001]]})]
        cls.tmp = tempfile.TemporaryDirectory()
        paths = []
        for name, feats in (("named", named), ("roads", roads)):
            path = os.path.join(cls.tmp.name, name + ".geojsonseq")
            with open(path, "w", encoding="utf-8") as fh:
                for f in feats:
                    fh.write("\x1e" + json.dumps(f, ensure_ascii=False) + "\n")
            paths.append(path)
        cls.osm = cc.load_osm(paths[0])
        cls.osm["roads"] = cc.load_roads(paths[1])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, p, others=()):
        return cc.check_poi(p, self.osm, [p, *others])

    def test_confirmed_pin(self):
        row = self.check(poi("a", "Hải Sản Đà Nẵng Bé Biển", "restaurant", self.lat0, self.lon0))
        self.assertEqual((row["verdict"], row["review"]), ("ok", ""))
        self.assertLess(row["dist_m"], 20)

    def test_landmark_500_m_away_is_p1(self):
        row = self.check(poi("b", "Nhà thờ Phú Thượng", "religious", self.lat0, self.lon0,
                             role="attraction"))
        self.assertEqual((row["verdict"], row["tier"], row["review"]), ("off", "1km", "P1"))
        self.assertTrue(400 < row["dist_m"] < 600)

    def test_far_business_namesake_backed_by_its_address_is_not_reviewed(self):
        p = poi("c", "Gyu Sachi - Nhà hàng nướng Nhật", "restaurant", self.lat0 + 0.0100, self.lon0,
                note="Mục cơ sở 54–56 Quang Trung phù hợp POI")
        row = self.check(p)
        self.assertEqual(row["verdict"], "ambiguous")
        self.assertIn("address_backs_pin", row["flags"])
        self.assertEqual(row["review"], "")

    def test_unknown_place_and_same_point(self):
        a = poi("d", "Khách Sạn Rose", "lodging", self.lat0 + 0.002, self.lon0, role="base")
        b = poi("e", "Hotel Hồng Phúc 2", "lodging", self.lat0 + 0.002, self.lon0 + 0.00001,
                role="base")
        row = self.check(a, [b])
        self.assertEqual(row["verdict"], "no_osm")
        self.assertIn("same_point_same_kind", row["flags"])
        self.assertEqual(row["review"], "P2")

    def test_road_distance(self):
        d = cc.road_distance(self.lat0 + 0.002, self.lon0, self.osm["roads"])
        self.assertAlmostEqual(d, 0.0019 * 110540.0, delta=5)
        self.assertEqual(cc.road_distance(self.lat0 + 0.5, self.lon0, self.osm["roads"]), math.inf)


if __name__ == "__main__":
    unittest.main()
