"""Unit test for weather labeler (T063-M4CODE). Deterministic rules + OSM smoke.

Real eval (macro-F1 >= 0.95) PENDING user I/O audit — see docs/weather-label.md.

Run from repo root: python BE/tests/unit/test_weather_label.py -v
"""

import json
import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.weather_label.labeler import (  # noqa: E402
    featurize,
    label,
    label_element,
    weather_evidence,
)

OSM_DN = os.path.join(os.environ.get("TEMP", "/tmp"), "opencode", "osm", "danang.json")


def el(tags: dict, typ: str = "node") -> dict:
    return {"type": typ, "tags": tags}


class TestWeatherLabel(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
