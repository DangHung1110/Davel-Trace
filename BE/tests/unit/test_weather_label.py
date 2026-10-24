"""Unit tests for the T063 weather labeler.

Covers the legacy v1 rules and the v2 pure snapshot-POI classifier
(`classify_poi`): audit precedence/conflicts, OSM R1 vs R2 evidence,
geometry/name linking, sun-only abstention, and weather_sensitive derivation.

Confidence is a HEURISTIC rule strength, NOT calibrated.  The real eval
(macro-F1 >= 0.95) remains PENDING the human I/O/B audit.

Run from repo root: python BE/tests/unit/test_weather_label.py -v
"""

import json
import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.weather_label.labeler import (  # noqa: E402
    classify_poi,
    classify_snapshot_poi,
    featurize,
    label,
    label_element,
    weather_evidence,
)

OSM_DN = os.path.join(os.environ.get("TEMP", "/tmp"), "opencode", "osm", "danang.json")
SNAPSHOT = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "snapshots", "danang-v1",
    "pois.json")

# A polygon around lat 16.0 / lon 108.0 (used for R1/R2 containment tests).
POLY = [
    {"lat": 15.99, "lon": 107.99},
    {"lat": 15.99, "lon": 108.01},
    {"lat": 16.01, "lon": 108.01},
    {"lat": 16.01, "lon": 107.99},
]
FAR_POLY = [
    {"lat": 16.20, "lon": 108.20},
    {"lat": 16.20, "lon": 108.21},
    {"lat": 16.21, "lon": 108.21},
    {"lat": 16.21, "lon": 108.20},
]


def el(tags: dict, typ: str = "node") -> dict:
    return {"type": typ, "tags": tags}


def poi(name="", cat="", typ="", tags=None, lat=None, lon=None, io_label=None) -> dict:
    d = {"name": name, "cat": cat, "type": typ or name, "tags": tags or []}
    if lat is not None:
        d["lat"] = lat
    if lon is not None:
        d["lon"] = lon
    if io_label is not None:
        d["io_label"] = io_label
    return d


def osm(tags: dict, typ="way", geometry=None, **meta) -> dict:
    d = {"type": typ, "id": 1, "tags": tags}
    if geometry is not None:
        d["geometry"] = geometry
    d.update(meta)
    return d


def sample(**kwargs):
    return classify_poi(poi(**kwargs))


class TestWeatherLabelV1(unittest.TestCase):
    """Legacy API must stay compatible for the existing smoke/wiring."""

    def test_tag_rules(self):
        self.assertEqual(label(featurize(el({"tourism": "museum"})))["label"], "indoor")
        self.assertEqual(label(featurize(el({"amenity": "cafe"})))["label"], "indoor")
        self.assertEqual(label(featurize(el({"tourism": "viewpoint"})))["label"], "outdoor")
        self.assertEqual(label(featurize(el({"leisure": "park"})))["label"], "outdoor")
        self.assertEqual(label(featurize(el({"amenity": "marketplace"})))["label"], "outdoor")
        self.assertEqual(label(featurize(el({"historic": "memorial"})))["label"], "outdoor")

    def test_name_keywords(self):
        r = label(featurize(el({"name": "Bãi biển Mỹ Khê"})))
        self.assertEqual((r["label"], r["rule"]), ("outdoor", "name-keyword"))
        r = label(featurize(el({"name": "Bảo tàng Chăm"})))
        self.assertEqual((r["label"], r["rule"]), ("indoor", "name-keyword"))

    def test_confidence_unclaimed(self):
        for tags in ({"amenity": "cafe"}, {"name": "X"}, {"tourism": "viewpoint"}):
            r = label(featurize(el(tags)))
            self.assertIn(r["confidence"], (0.9, 0.7, 0.5))

    def test_evidence_shape(self):
        ev = weather_evidence("Cafe", label_element(el({"amenity": "cafe"})))
        self.assertTrue(ev and "indoor" in ev[0])

    def test_osm_smoke_distribution(self):
        if not os.path.exists(OSM_DN):
            self.skipTest("OSM cache absent (fetch_osm.py first)")
        els = json.load(open(OSM_DN, encoding="utf-8"))["elements"]
        dist = Counter(label_element(e)["label"] for e in els)
        print(f"\n OSM DN n={len(els)}: {dict(dist)}")
        self.assertGreater(len(els), 1000)
        self.assertGreater(dist["indoor"], dist["outdoor"])  # DN nodes cafe-heavy


class TestClassifyPoiSchema(unittest.TestCase):
    def test_schema_and_alias(self):
        self.assertIs(classify_snapshot_poi, classify_poi)
        r = sample(name="Bảo tàng Chăm", cat="museum")
        for key in (
            "space", "space_source", "space_confidence", "space_evidence",
            "space_conflict", "rain_protection", "rain_protection_source",
            "rain_protection_confidence", "rain_protection_evidence",
            "weather_sensitive", "confidence_kind", "outdoor_exposure",
            "sun_exposure", "wind_exposure", "rain_cover", "exposure_source",
        ):
            self.assertIn(key, r)
        self.assertIn(r["space"], ("indoor", "outdoor", "both", "unknown"))
        self.assertIn(r["rain_protection"],
                      ("enclosed", "sheltered", "none", "unknown"))
        self.assertIsInstance(r["space_evidence"], list)
        self.assertIsInstance(r["space_conflict"], list)
        self.assertEqual(r["confidence_kind"], "heuristic_uncalibrated")

    def test_keyword_aliases(self):
        r = classify_poi(poi(name="X"), human_label="I",
                         osm_evidence=osm({"building": "roof"}, typ="node"))
        self.assertEqual((r["space"], r["space_source"]), ("indoor", "audit"))
        # The audit alone does not assert rain; the node's building=roof is
        # explicit OSM R2 evidence.
        self.assertEqual(r["rain_protection"], "sheltered")

        r = classify_poi(poi(name="X"), human_label="I")
        self.assertEqual(r["rain_protection"], "unknown")

    def test_nested_osm_evidence_payload_used(self):
        p = poi(name="Bảo tàng", lat=16.0, lon=108.005)
        p["osm_evidence"] = osm({"building": "yes", "name": "Bảo tàng"},
                                geometry=POLY)
        r = classify_poi(p)
        self.assertEqual((r["space"], r["space_source"]), ("indoor", "osm"))
        self.assertEqual(r["rain_protection"], "enclosed")

    def test_does_not_mutate_poi(self):
        p = poi(name="Bảo tàng Chăm", cat="museum")
        before = json.dumps(p, sort_keys=True)
        classify_poi(p)
        self.assertEqual(before, json.dumps(p, sort_keys=True))


class TestAuditPrecedence(unittest.TestCase):
    def test_audit_wins_and_conflict_is_metadata(self):
        p = poi(name="Bãi biển Mỹ Khê", cat="beach")
        r = classify_poi(p, audit="I", osm=osm({"natural": "beach"}))
        self.assertEqual((r["space"], r["space_source"]), ("indoor", "audit"))
        self.assertEqual(r["space_confidence"], 1.0)
        self.assertFalse(r["weather_sensitive"])
        self.assertTrue(r["space_conflict"])
        # Audit I/O/B is authoritative for space only; it must not assert rain
        # protection.  OSM here only proves an open beach.
        self.assertEqual((r["rain_protection"], r["rain_protection_source"]),
                         ("unknown", "unknown"))
        self.assertTrue(any("does not encode rain protection" in e
                            for e in r["rain_protection_evidence"]))

    def test_snapshot_io_label_is_used_when_audit_omitted(self):
        p = poi(name="Bảo tàng Chăm", cat="museum", io_label="O")
        r = classify_poi(p, osm=osm({"tourism": "museum"}))
        self.assertEqual((r["space"], r["space_source"]), ("outdoor", "audit"))
        self.assertEqual(r["space_confidence"], 1.0)
        self.assertTrue(r["weather_sensitive"])
        self.assertTrue(any("snapshot io_label=outdoor" in c
                            for c in r["space_conflict"]))

    def test_audit_both_maps_to_weather_sensitive(self):
        for audit, expected in (("I", False), ("O", True), ("B", True)):
            r = classify_poi(poi(name="X"), audit=audit)
            self.assertEqual(r["weather_sensitive"], expected)
            self.assertEqual(r["space_confidence"], 1.0)

    def test_snapshot_audit_labels_are_preserved(self):
        if not os.path.exists(SNAPSHOT):
            self.skipTest("snapshot absent")
        with open(SNAPSHOT, encoding="utf-8") as snapshot_file:
            pois = json.load(snapshot_file)["pois"]
        audited = [p for p in pois if p.get("io_label") in ("I", "O", "B")]
        self.assertEqual(len(audited), 46)
        expected = {"I": ("indoor", False), "O": ("outdoor", True),
                    "B": ("both", True)}
        for p in audited:
            space, weather = expected[p["io_label"]]
            r = classify_poi(p)
            self.assertEqual(r["space"], space)
            self.assertEqual(r["space_confidence"], 1.0)
            self.assertEqual(r["weather_sensitive"], weather)


class TestSpaceRules(unittest.TestCase):
    def test_committed_space_drives_exposure(self):
        indoor = classify_poi(poi(
            name="DD WONDERLAND", typ="Sân chơi trong nhà",
            cat="attraction"))
        self.assertEqual(indoor["space"], "indoor")
        self.assertLessEqual(indoor["outdoor_exposure"], 0.2)
        self.assertEqual(indoor["rain_cover"], "enclosed")

        rooftop = classify_poi(poi(
            name="Marine Sky Bar-Rooftop SeaView with Exclusive Spa Offers",
            typ="Quán bar", cat="bar"))
        self.assertEqual(rooftop["space"], "both")
        self.assertGreaterEqual(rooftop["outdoor_exposure"], 0.6)
        self.assertNotEqual(rooftop["rain_cover"], "enclosed")

        unknown = classify_poi(poi(name="Unclassified venue",
                                   cat="attraction"))
        self.assertEqual(unknown["space"], "unknown")
        self.assertEqual(unknown["rain_cover"], "unknown")
        for field in ("outdoor_exposure", "sun_exposure", "wind_exposure"):
            self.assertIsNone(unknown[field], field)

    def test_osmand_name_agree_outdoor_open(self):
        p = poi(name="Bãi biển Mỹ Khê", cat="beach")
        r = classify_poi(p, osm=osm({"natural": "beach"}))
        self.assertEqual((r["space"], r["space_source"]), ("outdoor", "osm"))
        self.assertEqual(r["space_confidence"], 0.8)
        self.assertEqual((r["rain_protection"], r["rain_protection_source"]),
                         ("none", "osm"))
        self.assertTrue(r["weather_sensitive"])

    def test_osmand_name_agree_indoor(self):
        p = poi(name="Bảo tàng Chăm", cat="museum", lat=16.0, lon=108.005)
        r = classify_poi(
            p, osm=osm({"tourism": "museum", "building": "yes",
                        "name": "Bảo tàng Chăm"}, geometry=POLY))
        self.assertEqual((r["space"], r["space_source"]), ("indoor", "osm"))
        self.assertEqual(r["space_confidence"], 0.8)
        self.assertEqual(r["rain_protection"], "enclosed")
        self.assertFalse(r["weather_sensitive"])

    def test_name_only_does_not_assert_rain(self):
        r = sample(name="Bãi biển Mỹ Khê")
        self.assertEqual((r["space"], r["space_source"]), ("outdoor", "name"))
        self.assertEqual(r["space_confidence"], 0.6)
        # Name keywords decide space only; they are not OSM rain evidence.
        self.assertEqual((r["rain_protection"], r["rain_protection_source"]),
                         ("unknown", "unknown"))

        r = sample(name="Bảo tàng Chăm")
        self.assertEqual((r["space"], r["space_source"]), ("indoor", "name"))
        self.assertEqual(r["rain_protection"], "unknown")

    def test_ambiguous_attraction_market_landmark_are_unknown(self):
        for name, cat in (("Điểm tham quan", "attraction"),
                          ("Landmark Đà Nẵng", "landmark")):
            r = sample(name=name, cat=cat)
            self.assertEqual((r["space"], r["space_source"]),
                             ("unknown", "canonical"))
            self.assertEqual(r["space_confidence"], 0.4)
            self.assertEqual(r["rain_protection"], "unknown")
            self.assertTrue(r["weather_sensitive"])

        # A market hall is roofed but open-sided: both, never unknown/outdoor.
        r = sample(name="Chợ Hàn", cat="market")
        self.assertEqual((r["space"], r["space_source"]), ("both", "name"))

    def test_no_blanket_indoor_default(self):
        r = classify_poi({})
        self.assertEqual(r["space"], "unknown")
        self.assertEqual(r["space_source"], "canonical")
        self.assertEqual(r["space_confidence"], 0.4)
        self.assertTrue(r["weather_sensitive"])

    def test_osmand_ambiguous_tag_does_not_infer(self):
        r = classify_poi(poi(name="X"), osm=osm({"tourism": "attraction"}))
        self.assertEqual(r["space"], "unknown")
        self.assertTrue(any("ambiguous OSM tag" in n
                            for n in r["rain_protection_evidence"]))

    def test_both_requires_audit_or_explicit_evidence(self):
        r = classify_poi(poi(name="X"), audit="B")
        self.assertEqual((r["space"], r["space_source"]), ("both", "audit"))
        self.assertTrue(r["weather_sensitive"])

        r = classify_poi(poi(name="X"), osm=osm({"indoor": "yes",
                                                 "outdoor": "yes"}))
        self.assertEqual((r["space"], r["space_source"]), ("both", "osm"))
        self.assertEqual(r["space_confidence"], 0.7)
        self.assertTrue(r["weather_sensitive"])

        # R2 partial roof is not "both".
        r = classify_poi(poi(name="X"), osm=osm({"building": "roof"}, typ="node"))
        self.assertNotEqual(r["space"], "both")
        self.assertEqual(r["rain_protection"], "sheltered")

        # Audited both + explicit cover still records R2 rain protection.
        r = classify_poi(poi(name="X"), audit="B",
                         osm=osm({"covered": "yes"}, typ="node"))
        self.assertEqual((r["space"], r["rain_protection"]),
                         ("both", "sheltered"))


class TestVietnameseNameMatching(unittest.TestCase):
    """QA regressions: accent-only look-alikes and compound/brand names."""

    def test_address_and_brand_words_do_not_flip_cafes_or_hotels(self):
        cases = (
            ("Coffee Trà, 51 Lý Đạo Thành, Mân Thái", "cafe"),
            ("Tiệm cà phê Cậu Út", "cafe"),
            ("Seavitel Beach Hotel - DaNang", "lodging"),
        )
        for name, cat in cases:
            r = sample(name=name, cat=cat)
            self.assertEqual((r["space"], r["space_source"]),
                             ("indoor", "name"), name)

    def test_fresh_vs_river_and_market_hall(self):
        r = sample(name="Chợ hải sản tươi sống biển Thanh Khê", cat="market")
        self.assertEqual((r["space"], r["space_source"]), ("both", "name"))
        self.assertEqual(r["space_confidence"], 0.6)

    def test_beer_garden_is_both(self):
        r = sample(name="MÊ Ê Ê Beer Garden - 316 Hà Huy Tập", cat="bar")
        self.assertEqual((r["space"], r["space_source"]), ("both", "name"))

    def test_pagoda_and_church_compounds_are_both(self):
        for name, cat in (("Chùa An Long", "landmark"),
                          ("Nhà Thờ Giáo Xứ Hòa Thuận", "landmark"),
                          ("Chùa Hương Sơn", "landmark")):
            r = sample(name=name, cat=cat)
            self.assertEqual((r["space"], r["space_source"]),
                             ("both", "name"), name)

    def test_decisive_landmark_and_beach_names(self):
        for name, cat, want in (
                ("Bãi Tắm Non Nước", "attraction", "outdoor"),
                ("Memorial to the victims of Flight 229", "landmark", "outdoor"),
                ("Tượng đài Dũng sĩ Điện Ngọc", "landmark", "outdoor")):
            r = sample(name=name, cat=cat)
            self.assertEqual((r["space"], r["space_source"]),
                             (want, "name"), name)

    def test_accent_guard_is_not_fooled_by_unaccented_lookalikes(self):
        from BE.ml.weather_label.labeler import _has_kw  # noqa: PLC0415
        self.assertTrue(_has_kw("Đảo Cù Lao Chàm", "dao"))
        self.assertFalse(_has_kw("51 Lý Đạo Thành", "dao"))
        self.assertTrue(_has_kw("Cầu Rồng", "cau"))
        self.assertFalse(_has_kw("Tiệm cà phê Cậu Út", "cau"))
        self.assertTrue(_has_kw("Sông Hàn", "song"))
        self.assertFalse(_has_kw("hải sản tươi sống", "song"))


class TestConflict(unittest.TestCase):
    def test_osmand_vs_name_conflict_downgrades_confidence(self):
        p = poi(name="Bãi biển Mỹ Khê", cat="beach")
        r = classify_poi(p, osm=osm({"tourism": "museum"}))
        self.assertEqual((r["space"], r["space_source"]), ("indoor", "osm"))
        self.assertEqual(r["space_confidence"], 0.3)
        # OSM category tags inform space but are not rain evidence.
        self.assertEqual(r["rain_protection"], "unknown")
        self.assertTrue(r["space_conflict"])
        self.assertTrue(r["weather_sensitive"])  # conf < 0.5 is conservative

    def test_osmand_internal_conflict_abstains(self):
        r = classify_poi(poi(name="X"),
                         osm=osm({"tourism": "museum", "leisure": "park"}))
        self.assertEqual((r["space"], r["space_source"]), ("unknown", "osm"))
        self.assertEqual(r["space_confidence"], 0.3)
        self.assertTrue(r["space_conflict"])


class TestGeometryAndRain(unittest.TestCase):
    def test_r1_name_linked_building_polygon_is_enclosed(self):
        p = poi(name="Bảo tàng", lat=16.0, lon=108.005)
        e = osm({"building": "yes", "name": "Bảo tàng"}, geometry=POLY)
        r = classify_poi(p, osm=e)
        self.assertEqual((r["space"], r["space_source"]), ("indoor", "osm"))
        self.assertEqual(r["space_confidence"], 0.8)
        self.assertEqual((r["rain_protection"], r["rain_protection_source"]),
                         ("enclosed", "osm"))
        self.assertEqual(r["rain_protection_confidence"], 0.7)

    def test_r2_roof_is_sheltered_not_enclosed(self):
        p = poi(name="Mái che", lat=16.0, lon=108.005)
        e = osm({"building": "roof", "name": "Mái che"}, geometry=POLY)
        r = classify_poi(p, osm=e)
        self.assertEqual(r["space"], "outdoor")
        self.assertEqual((r["rain_protection"], r["rain_protection_source"]),
                         ("sheltered", "osm"))

        # A category tag does not turn a roof-only structure into R1.
        r = classify_poi(poi(name="X"),
                         osm=osm({"building": "roof", "amenity": "cafe"},
                                 typ="node"))
        self.assertEqual((r["space"], r["rain_protection"]),
                         ("outdoor", "sheltered"))

    def test_r2_covered_and_shelter_tags(self):
        for tags in ({"covered": "yes"},
                     {"amenity": "shelter"},
                     {"amenity": "weather_shelter"},
                     {"roof": "yes"},
                     {"awning": "yes"},
                     {"canopy": "yes"}):
            r = classify_poi(poi(name="Nhà chờ"), osm=osm(tags, typ="node"))
            self.assertEqual(r["rain_protection"], "sheltered", tags)
            self.assertEqual(r["space"], "outdoor", tags)

    def test_indoor_and_location_indoor_are_enclosed(self):
        for tags in ({"indoor": "yes"}, {"location": "indoor"}):
            r = classify_poi(poi(name="X"), osm=osm(tags, typ="node"))
            self.assertEqual((r["space"], r["rain_protection"]),
                             ("indoor", "enclosed"), tags)

    def test_node_only_cache_is_not_geometry(self):
        p = poi(name="POI", lat=16.0, lon=108.005)
        r = classify_poi(p, osm=osm({"building": "yes"}, typ="node"))
        self.assertEqual(r["space"], "unknown")
        self.assertEqual(r["rain_protection"], "unknown")

    def test_proximity_is_not_inferred(self):
        p = poi(name="Điểm tham quan", cat="attraction", lat=16.0, lon=108.005)
        e = osm({"building": "yes", "name": "Another Building"},
                geometry=FAR_POLY)
        r = classify_poi(p, osm=e)
        self.assertEqual(r["space"], "unknown")
        self.assertEqual(r["rain_protection"], "unknown")
        self.assertTrue(any("unlinked OSM element ignored" in n
                            for n in r["rain_protection_evidence"]))

    def test_anonymous_non_containing_polygon_is_not_linked(self):
        p = poi(name="X", lat=16.0, lon=108.005)
        r = classify_poi(p, osm=osm({"building": "yes"}, geometry=FAR_POLY))
        self.assertEqual(r["space"], "unknown")

    def test_clear_open_feature_is_none(self):
        r = classify_poi(poi(name="Công viên"), osm=osm({"leisure": "park"}))
        self.assertEqual((r["space"], r["rain_protection"]),
                         ("outdoor", "none"))

    def test_absent_rain_evidence_is_unknown_not_none(self):
        # A bridge is outdoor, but nothing proves it lacks a cover.
        r = classify_poi(poi(name="Cầu Rồng"), osm=osm({"man_made": "bridge"}))
        self.assertEqual(r["space"], "outdoor")
        self.assertEqual(r["rain_protection"], "unknown")

    def test_sun_only_is_not_rain_protection(self):
        r = classify_poi(poi(name="Pergola"), osm=osm({"shade": "yes"}, typ="node"))
        self.assertEqual(r["space"], "unknown")
        self.assertEqual(r["rain_protection"], "unknown")
        self.assertTrue(any("sun-only tag" in n
                            for n in r["rain_protection_evidence"]))

        # A name keyword and canonical category do not assert rain either.
        r = classify_poi(poi(name="Quán cà phê Pergola", cat="cafe"))
        self.assertEqual(r["space"], "indoor")
        self.assertEqual(r["rain_protection"], "unknown")
        self.assertTrue(any("sun-only name keyword" in n
                            for n in r["rain_protection_evidence"]))

        # A named "sun shelter" alone is not R2 rain protection.
        r = classify_poi(
            poi(name="Sun shelter"),
            osm=osm({"amenity": "shelter", "name": "Sun shelter"}, typ="node"))
        self.assertEqual(r["rain_protection"], "unknown")

    def test_covered_open_feature_prefers_sheltered(self):
        r = classify_poi(poi(name="Công viên có mái"),
                         osm=osm({"leisure": "park", "covered": "yes"}))
        self.assertEqual(r["space"], "outdoor")
        self.assertEqual(r["rain_protection"], "sheltered")


class TestRainRequiresOsmEvidence(unittest.TestCase):
    """Rain R1/R2/none must come from linked OSM evidence, never audit/name."""

    def test_audit_alone_does_not_assert_rain(self):
        for audit in ("I", "O", "B"):
            r = classify_poi(poi(name="X"), audit=audit)
            self.assertEqual(r["rain_protection"], "unknown", audit)
            self.assertEqual(r["rain_protection_source"], "unknown", audit)
            self.assertTrue(any("does not encode rain protection" in e
                                for e in r["rain_protection_evidence"]), audit)

    def test_name_and_canonical_alone_do_not_assert_rain(self):
        cases = (
            ("Bảo tàng Chăm", "museum", "indoor"),
            ("Bãi biển Mỹ Khê", "beach", "outdoor"),
            ("Công viên", "park", "outdoor"),
            ("Quán ăn", "restaurant", "indoor"),
        )
        for name, cat, space in cases:
            r = classify_poi(poi(name=name, cat=cat))
            self.assertEqual(r["space"], space, (name, cat))
            self.assertEqual(r["rain_protection"], "unknown", (name, cat))

    def test_r1_requires_explicit_indoor_or_actual_polygon(self):
        for tags in ({"indoor": "yes"}, {"location": "indoor"},
                     {"enclosed": "yes"}):
            r = classify_poi(poi(name="X"), osm=osm(tags, typ="node"))
            self.assertEqual(r["rain_protection"], "enclosed", tags)

        p = poi(name="Bảo tàng", lat=16.0, lon=108.005)
        r = classify_poi(p, osm=osm({"building": "yes"}, geometry=POLY))
        self.assertEqual(r["rain_protection"], "enclosed")

    def test_r2_requires_explicit_cover_evidence(self):
        for tags in ({"building": "roof"}, {"covered": "yes"},
                     {"roof": "yes"}, {"awning": "yes"}, {"canopy": "yes"},
                     {"amenity": "weather_shelter"},
                     {"weather_protection": "roof"},
                     {"weather_protection": "awning"},
                     {"weather_protection": "canopy"}):
            r = classify_poi(poi(name="X"), osm=osm(tags, typ="node"))
            self.assertEqual(r["rain_protection"], "sheltered", tags)

    def test_way_type_alone_is_not_polygon_evidence(self):
        r = classify_poi(poi(name="X"),
                         osm=osm({"building": "yes"}, typ="way"))
        self.assertEqual(r["rain_protection"], "unknown")

        r = classify_poi(poi(name="X"),
                         osm=osm({"building": "no"}, typ="way"))
        self.assertEqual(r["rain_protection"], "unknown")

        # Explicit linked-polygon metadata supplied by the caller qualifies.
        r = classify_poi(poi(name="X"),
                         osm=osm({"building": "yes"}, typ="way",
                                 name_linked=True))
        self.assertEqual(r["rain_protection"], "enclosed")

    def test_sun_shelter_is_not_rain_shelter(self):
        cases = (
            {"amenity": "shelter", "shelter_type": "sun_shelter"},
            {"amenity": "shelter", "sun_shelter": "yes"},
            {"amenity": "shelter", "shelter": "sun"},
            {"amenity": "shelter", "shade": "yes"},
            {"amenity": "shelter", "natural": "tree"},
            {"amenity": "shelter", "man_made": "pergola"},
            {"amenity": "shelter", "name": "Sun shelter"},
        )
        for tags in cases:
            r = classify_poi(poi(name=tags.get("name", "X")),
                             osm=osm(tags, typ="node"))
            self.assertEqual(r["rain_protection"], "unknown", tags)
            self.assertTrue(any("sun-only" in n
                                for n in r["rain_protection_evidence"]), tags)


class TestWeatherSensitive(unittest.TestCase):
    def test_derivation(self):
        # Confident indoor -> False.
        r = classify_poi(poi(name="Bảo tàng"), osm=osm({"tourism": "museum"}))
        self.assertFalse(r["weather_sensitive"])

        # Outdoor / both / unknown -> True.
        self.assertTrue(sample(name="Bãi biển")["weather_sensitive"])
        self.assertTrue(classify_poi(poi(name="X"), audit="B")["weather_sensitive"])
        self.assertTrue(classify_poi({})["weather_sensitive"])

        # Canonical indoor is only 0.4 -> conservative True.
        r = classify_poi(poi(name="Quán ăn", cat="restaurant"))
        self.assertEqual((r["space"], r["space_confidence"]), ("indoor", 0.6))
        # Name-only is 0.6, so this one is confident enough to be False.
        self.assertFalse(r["weather_sensitive"])

        r = classify_poi(poi(cat="restaurant"))
        self.assertEqual((r["space"], r["space_confidence"]), ("indoor", 0.4))
        self.assertTrue(r["weather_sensitive"])

        # Conflict 0.3 -> True.
        r = classify_poi(poi(name="Bãi biển Mỹ Khê"), osm=osm({"tourism": "museum"}))
        self.assertTrue(r["weather_sensitive"])


if __name__ == "__main__":
    unittest.main()
