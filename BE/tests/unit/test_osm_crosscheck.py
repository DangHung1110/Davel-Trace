"""Unit test: OSM cross-check, field by field (Phase 4, tier 1).

Covers: name matching (folded, address tail dropped, equal sets or >= 2
shared words in order with one distinctive word), distance to geometry
(a long beach, inside a polygon), OSM opening_hours parsing (24/7, weekday
rules, off days, overnight, unparsed), hours and category statuses,
same-source POIs never confirm themselves, a category conflict keeps
exists single, two POIs on one OSM object are flagged, and the committed
sidecar covers every snapshot POI.

Run from repo root: python BE/tests/unit/test_osm_crosscheck.py -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.data.osm_crosscheck import (  # noqa: E402
    FORMAT, category_status, compare_hours, core_name, crosscheck, distance_m,
    load_features, name_score, parse_osm_hours)

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "snapshots",
                            "danang-v1")
H = 60


def feature(fid, name, tags, geometry):
    return json.dumps({"type": "Feature", "id": fid, "geometry": geometry,
                       "properties": {"name": name, **tags}})


def point(lat, lon):
    return {"type": "Point", "coordinates": [lon, lat]}


class TestNames(unittest.TestCase):
    def test_core_name_drops_address_tail(self):
        self.assertEqual(core_name("Quán Mỳ Quảng Bà Mua - 58 Ông Ích Đường"),
                         "Quán Mỳ Quảng Bà Mua")
        self.assertEqual(core_name("Nhà Mình Spa cơ sở 2 462 Điện Biên Phủ"),
                         "Nhà Mình Spa cơ sở 2")
        self.assertEqual(core_name("Bảo tàng 3D Art In Paradise"),
                         "Bảo tàng 3D Art In Paradise")
        self.assertEqual(core_name("Quán lẩu 70"), "Quán lẩu 70")

    def test_name_score(self):
        self.assertEqual(name_score("Bãi biển Mỹ Khê", ["Mỹ Khê Beach"]), 1.0)
        self.assertGreaterEqual(name_score("Động Vân Thông", ["Van Thong Cave"]), 0.6)
        self.assertEqual(name_score("Bảo tàng Điêu khắc Chăm Đà Nẵng",
                                    ["Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng"]), 1.0)
        # one shared word, swapped order, place names only, dish only: no match
        self.assertEqual(name_score("Bãi tắm Sao Biển", ["Nhà thờ Đức Mẹ Sao Biển"]), 0)
        self.assertEqual(name_score("Trà Sơn Quán", ["Son Tra Viewpoint"]), 0)
        self.assertEqual(name_score("Son Tra Retreat", ["Son Tra Viewpoint"]), 0)
        self.assertEqual(name_score("Bảo tàng Đà Nẵng", ["Bảo tàng Mỹ thuật Đà Nẵng"]), 0)
        self.assertEqual(name_score("Mỳ Quảng Quê Xưa", ["My Quang Restaurant"]), 0)
        self.assertEqual(name_score("Nhà Mình Spa cơ sở 2 462 Điện Biên Phủ",
                                    ["YODY Điện Biên Phủ"]), 0)


class TestGeometry(unittest.TestCase):
    def test_distance_to_line_not_centre(self):
        beach = {"type": "LineString", "coordinates": [[108.24, 16.00], [108.26, 16.06]]}
        self.assertLess(distance_m(16.03, 108.2502, beach), 30)
        self.assertGreater(distance_m(16.03, 108.26, beach), 500)

    def test_inside_polygon_is_zero(self):
        park = {"type": "Polygon", "coordinates": [[[108.0, 16.0], [108.01, 16.0],
                                                    [108.01, 16.01], [108.0, 16.01],
                                                    [108.0, 16.0]]]}
        self.assertEqual(distance_m(16.005, 108.005, park), 0.0)


class TestOsmHours(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_osm_hours("24/7")[3], [(0, 24 * H)])
        week = parse_osm_hours("Tu-Th 08:00-12:00,14:00-16:30; Sa-Su 08:00-12:00,14:00-16:30")
        self.assertEqual(week[0], [])
        self.assertEqual(week[1], [(8 * H, 12 * H), (14 * H, 16 * H + 30)])
        self.assertEqual(parse_osm_hours("Mo-Su 18:00-02:00")[0], [(18 * H, 26 * H)])
        self.assertEqual(parse_osm_hours("Th-Tu 11:00-12:00")[2], [])  # wraps past Su
        self.assertEqual(parse_osm_hours("Mo-Fr 08:00-17:00; Sa off")[5], [])
        self.assertIsNone(parse_osm_hours("Mo-Su 13:00+"))
        self.assertIsNone(parse_osm_hours("sunrise-sunset"))

    def test_compare(self):
        poi = {"opening_hours": ["07:00-22:00"]}
        self.assertEqual(compare_hours(poi, "Mo-Su 07:30-21:45")[0], "confirmed")
        self.assertEqual(compare_hours(poi, "Mo-Su 16:00-23:00")[0], "conflict")
        self.assertEqual(compare_hours(poi, None)[0], "single")
        self.assertEqual(compare_hours({"opening_hours": []}, "Mo-Su 08:00-17:00")[0],
                         "osm_only")
        self.assertEqual(compare_hours({"opening_hours": []}, None)[0], "missing")
        self.assertEqual(compare_hours({"opening_hours": ["08:00-17:00"],
                                        "hours_source": "osm-converted"},
                                       "Mo-Su 08:00-17:00")[0], "same_source")
        status, ev = compare_hours({"opening_hours": ["08:00-12:00, 14:00-16:30"]},
                                   "Tu-Su 08:00-12:00,14:00-16:30")
        self.assertEqual((status, ev["osm_closed_days"]), ("confirmed", ["Mo"]))


class TestCategory(unittest.TestCase):
    def test_status(self):
        self.assertEqual(category_status("museum", {"tourism": "museum"})[0], "confirmed")
        self.assertEqual(category_status("attraction", {"natural": "beach"})[0], "conflict")
        # generic tags confirm, never refute
        self.assertEqual(category_status("market", {"tourism": "attraction"})[0], "single")
        self.assertEqual(category_status("landmark", {"tourism": "attraction"})[0],
                         "confirmed")
        self.assertEqual(category_status("museum", {"tourism": "museum", "shop": "gift"})[0],
                         "confirmed")
        self.assertEqual(category_status("cafe", {})[0], "single")


class TestCrosscheck(unittest.TestCase):
    def setUp(self):
        beach_line = {"type": "LineString",
                      "coordinates": [[108.24, 16.00], [108.26, 16.06]]}
        lines = [
            feature("w1", "Bãi biển Mỹ Khê", {"natural": "beach"}, beach_line),
            feature("n2", "Bảo tàng Chăm", {"tourism": "museum",
                                            "opening_hours": "Mo-Su 07:00-17:00"},
                    point(16.0603, 108.2233)),
            feature("n3", "Bãi Sủng Cỏ", {"natural": "beach"}, point(16.12, 108.30)),
            feature("n4", "Chợ Đêm", {"amenity": "marketplace"}, point(16.10, 108.25)),
        ]
        self.features = load_features(lines)

    def test_rows(self):
        pois = [
            {"poi_id": "beach", "name": "My Khe Beach", "cat": "beach",
             "lat": 16.03, "lon": 108.2502, "opening_hours": []},
            {"poi_id": "beach2", "name": "Bãi biển Mỹ Khê", "cat": "beach",
             "lat": 16.031, "lon": 108.2505, "opening_hours": []},
            {"poi_id": "museum", "name": "Bảo tàng Điêu khắc Chăm", "cat": "museum",
             "lat": 16.0604, "lon": 108.2233, "opening_hours": ["07:00-17:00"]},
            {"poi_id": "cove", "name": "Bãi Sủng Cỏ", "cat": "attraction",
             "lat": 16.12, "lon": 108.3001, "opening_hours": ["00:00-23:59"]},
            {"poi_id": "osm:node/4", "name": "Chợ Đêm", "cat": "market",
             "source": "osm/overpass", "lat": 16.10, "lon": 108.25,
             "opening_hours": []},
            {"poi_id": "far", "name": "Bảo tàng Điêu khắc Chăm", "cat": "museum",
             "lat": 16.07, "lon": 108.2233, "opening_hours": []},
        ]
        rows = crosscheck(pois, self.features)
        self.assertEqual(rows["beach"]["fields"]["exists"], "confirmed")
        self.assertEqual(rows["beach"]["duplicate_of"], ["beach2"])
        self.assertEqual(rows["museum"]["fields"],
                         {"exists": "confirmed", "location": "confirmed",
                          "category": "confirmed", "hours": "confirmed"})
        self.assertEqual(rows["cove"]["fields"]["category"], "conflict")
        self.assertEqual(rows["cove"]["fields"]["exists"], "single")
        self.assertEqual(rows["osm:node/4"]["fields"]["exists"], "same_source")
        self.assertIsNone(rows["far"]["match"])


class TestCommittedSidecar(unittest.TestCase):
    def test_sidecar_covers_the_snapshot(self):
        with open(os.path.join(SNAPSHOT_DIR, "pois.json"), encoding="utf-8") as f:
            ids = {p["poi_id"] for p in json.load(f)["pois"]}
        with open(os.path.join(SNAPSHOT_DIR, "osm_crosscheck.json"), encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(doc["format"], FORMAT)
        self.assertEqual(set(doc["pois"]), ids)
        counts = doc["summary"]["all"]["fields"]["exists"]
        self.assertEqual(sum(counts.values()), len(ids))


if __name__ == "__main__":
    unittest.main()
