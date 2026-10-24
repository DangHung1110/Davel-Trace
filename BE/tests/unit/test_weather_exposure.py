"""Unit tests for T063b continuous exposure attributes.

Covers the derivation precedence (human audit > OSM evidence > type default >
unknown), intermediate values for mixed-use categories, the PATM feature
wiring (antisymmetric, type fallback) and the distribution report gate: no new
``smart_tags`` field may collapse to a single value (entropy 0).  A distribution
report JSON+MD is written by ``write_reports``.

Run from repo root:
    python -m unittest BE.tests.unit.test_weather_exposure -v
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", ".."))
sys.path.insert(0, REPO_ROOT)

from BE.ml.data.enrich_snapshot import (  # noqa: E402
    EXPOSURE_JSON,
    EXPOSURE_MD,
    build_osm_by_poi,
    enrich,
    exposure_distribution,
    load_osm_cache,
    merge_audit_decisions,
    parse_audit,
    write_reports,
)
from BE.ml.weather_label.labeler import (  # noqa: E402
    EXPOSURE_FIELDS,
    derive_exposure,
    type_exposure,
)

SNAPSHOT = os.path.join(REPO_ROOT, "BE", "data", "snapshots", "danang-v1")
POIS_PATH = os.path.join(SNAPSHOT, "pois.json")
SPOT_CHECK = os.path.join(SNAPSHOT, "SPOT_CHECK.md")

FLOAT_FIELDS = ("outdoor_exposure", "sun_exposure", "wind_exposure")


class TestDeriveExposure(unittest.TestCase):
    def test_type_defaults(self):
        beach = type_exposure("beach")
        self.assertGreaterEqual(beach["outdoor_exposure"], 0.9)
        self.assertEqual(beach["rain_cover"], "open")

        museum = type_exposure("museum")
        self.assertLessEqual(museum["outdoor_exposure"], 0.1)
        self.assertEqual(museum["rain_cover"], "enclosed")

    def test_mixed_use_categories_stay_intermediate(self):
        for cat in ("attraction", "landmark", "market"):
            exp = derive_exposure(cat=cat)
            self.assertTrue(0.3 <= exp["outdoor_exposure"] <= 0.8, cat)
            self.assertEqual(exp["rain_cover"], "mixed", cat)
            self.assertEqual(exp["exposure_source"], "type", cat)

    def test_audit_beats_osm_and_type(self):
        exp = derive_exposure(audit_space="indoor", osm_space="outdoor",
                              osm_rain="none", cat="beach")
        self.assertEqual(exp["exposure_source"], "audit")
        self.assertLessEqual(exp["outdoor_exposure"], 0.1)
        self.assertEqual(exp["rain_cover"], "enclosed")

        out = derive_exposure(audit_space="outdoor", cat="museum")
        self.assertEqual(out["exposure_source"], "audit")
        self.assertGreaterEqual(out["outdoor_exposure"], 0.9)
        self.assertEqual(out["rain_cover"], "open")

    def test_osm_beats_type(self):
        exp = derive_exposure(osm_space="outdoor", cat="museum")
        self.assertEqual(exp["exposure_source"], "osm")
        self.assertGreaterEqual(exp["outdoor_exposure"], 0.85)

    def test_osm_rain_sharpens_rain_cover(self):
        covered = derive_exposure(osm_rain="sheltered", cat="beach")
        self.assertEqual(covered["rain_cover"], "covered")
        self.assertEqual(covered["exposure_source"], "osm")
        self.assertLessEqual(covered["sun_exposure"], 0.3)
        self.assertLessEqual(covered["wind_exposure"], 0.4)

        open_ = derive_exposure(osm_rain="none", cat="museum")
        self.assertEqual(open_["rain_cover"], "open")
        self.assertGreaterEqual(open_["outdoor_exposure"], 0.85)

    def test_unknown_is_missing_not_neutral(self):
        exp = derive_exposure(cat="unmapped-category")
        self.assertEqual(exp["exposure_source"], "unknown")
        self.assertEqual(exp["rain_cover"], "unknown")
        for key in FLOAT_FIELDS:
            self.assertIsNone(exp[key])

    def test_floats_in_unit_interval(self):
        cases = [
            dict(cat="beach"), dict(cat="museum"), dict(audit_space="both"),
            dict(osm_space="indoor"), dict(osm_rain="enclosed"),
            dict(audit_space="outdoor", osm_rain="sheltered"),
        ]
        for case in cases:
            exp = derive_exposure(**case)
            for key in FLOAT_FIELDS:
                self.assertGreaterEqual(exp[key], 0.0, (case, key))
                self.assertLessEqual(exp[key], 1.0, (case, key))
            self.assertIn(exp["rain_cover"],
                          ("enclosed", "covered", "mixed", "open", "unknown"))


class TestOsmCacheJoin(unittest.TestCase):
    def test_blind_audit_export_overrides_by_poi_id(self):
        pois = [{"poi_id": "p1", "name": "POI one"}]
        merged = merge_audit_decisions(
            pois, {"POI one": "I"}, {"p1": "outdoor"})
        self.assertEqual(merged["POI one"], "O")
        self.assertEqual(merged["p1"], "O")

    def _write_cache(self, directory: str, payload) -> str:
        path = os.path.join(directory, "osm.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        return path

    def test_join_requires_name_match_not_proximity(self):
        pois = [
            {"poi_id": "a", "name": "Bãi biển Mỹ Khê", "cat": "beach",
             "osm_evidence": {"osm": "node/1", "dist_m": 8.0}},
            {"poi_id": "b", "name": "Chợ Hàn", "cat": "market",
             "osm_evidence": {"osm": "node/2", "dist_m": 9.0}},
        ]
        elements = [
            {"type": "node", "id": 1, "tags": {"name": "Bãi biển Mỹ Khê",
                                               "natural": "beach"}},
            {"type": "node", "id": 2, "tags": {"name": "CaPhe Huy",
                                               "amenity": "cafe"}},
        ]
        by_poi = build_osm_by_poi(pois, elements)
        self.assertEqual(set(by_poi), {"a"})
        self.assertTrue(by_poi["a"]["name_linked"])

    def test_osm_space_path_fires_with_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = self._write_cache(tmp, {"elements": [
                {"type": "node", "id": 1,
                 "tags": {"name": "Bãi biển Mỹ Khê", "natural": "beach"}},
            ]})
            elements = load_osm_cache(cache)
        pois = [{"poi_id": "a", "name": "Bãi biển Mỹ Khê", "cat": "beach",
                 "osm_evidence": {"osm": "node/1"}}]
        report = enrich(pois, {}, build_osm_by_poi(pois, elements))
        self.assertEqual(pois[0]["space_source"], "osm")
        self.assertEqual(report["space_sources"].get("osm"), 1)
        self.assertEqual(report["osm_evidence_linked"], 1)

    def test_cache_accepts_bare_element_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = self._write_cache(tmp, [
                {"type": "node", "id": 7, "tags": {"natural": "beach"}},
            ])
            elements = load_osm_cache(cache)
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0]["id"], 7)


class TestSnapshotExposureDistribution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(POIS_PATH):
            raise unittest.SkipTest("snapshot absent")
        with open(POIS_PATH, encoding="utf-8") as f:
            cls.pois = copy.deepcopy(json.load(f)["pois"])
        cls.audit = parse_audit(SPOT_CHECK)
        cls.report = enrich(cls.pois, cls.audit)

    def test_every_poi_gets_all_fields(self):
        for poi in self.pois:
            st = poi["smart_tags"]
            for field in EXPOSURE_FIELDS:
                self.assertIn(field, st, poi.get("poi_id"))
            for field in FLOAT_FIELDS:
                if st.get("space") == "unknown":
                    self.assertIsNone(st[field], poi.get("poi_id"))
                else:
                    self.assertIsInstance(st[field], float, poi.get("poi_id"))
            if st.get("space") == "unknown":
                self.assertEqual(st["rain_cover"], "unknown", poi.get("poi_id"))
            if st.get("space") == "outdoor":
                self.assertNotEqual(st["rain_cover"], "enclosed", poi.get("poi_id"))

    def test_no_new_field_collapses_to_one_value(self):
        dist = self.report["exposure_distribution"]
        for field in EXPOSURE_FIELDS:
            stats = dist[field]
            self.assertGreater(stats["distinct"], 1, field)
            self.assertGreater(stats["entropy_bits"], 0.0, field)

    def test_report_writes_json_and_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = write_reports(tmp, self.report, "2026-10-21")
            for path in (outputs["exposure_json"], outputs["exposure_md"]):
                self.assertTrue(os.path.exists(path), path)
            with open(outputs["exposure_json"], encoding="utf-8") as f:
                payload = json.load(f)
            dist = payload["exposure_distribution"]
            for field in EXPOSURE_FIELDS:
                self.assertIn("distinct", dist[field])
                self.assertIn("entropy_bits", dist[field])
            with open(outputs["exposure_md"], encoding="utf-8") as f:
                md = f.read()
            self.assertIn("entropy", md)
            self.assertEqual(os.path.basename(outputs["exposure_json"]),
                             EXPOSURE_JSON)
            self.assertEqual(os.path.basename(outputs["exposure_md"]),
                             EXPOSURE_MD)

    def test_distribution_helper_matches_report(self):
        self.assertEqual(exposure_distribution(self.pois),
                         self.report["exposure_distribution"])


if __name__ == "__main__":
    unittest.main()
