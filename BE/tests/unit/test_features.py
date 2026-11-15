"""Unit test for transition features (T026). Stdlib unittest, seed-based.

Run from repo root: python BE/tests/unit/test_features.py -v
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.patm.features import FEATURE_NAMES, N_FEATURES, extract  # noqa: E402
from BE.ml.patm.make_pairs import load_pois  # noqa: E402

SNAPSHOT_DIR = os.path.join("data", "snapshots", "danang-v1")


class TestFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pois = {p["poi_id"]: p for p in load_pois(SNAPSHOT_DIR)}
        cls.a = cls.pois["son-tra"]
        cls.b = cls.pois["my-khe"]

    def test_21_features_unique_names(self):
        self.assertEqual(N_FEATURES, 21)
        self.assertEqual(len(set(FEATURE_NAMES)), 21)
        self.assertEqual(len(extract(self.a, self.b)), 21)
        self.assertEqual(FEATURE_NAMES[16], "prior_logp")
        self.assertEqual(FEATURE_NAMES[17:], (
            "x_outdoor_exposure", "x_rain_cover", "x_sun_exposure",
            "x_wind_exposure"))

    def test_prior_logp_directional_finite(self):
        from BE.ml.patm.features import FEATURE_NAMES as FN
        i = list(FN).index("prior_logp")
        fwd, back = extract(self.a, self.b)[i], extract(self.b, self.a)[i]
        self.assertTrue(all(abs(v) < 1e6 for v in (fwd, back)))
        # directional signal exists (not constant across orders)
        self.assertNotEqual(round(fwd, 6), round(back, 6))

    def test_no_absolute_poi_id(self):
        with open(os.path.join("BE", "ml", "patm", "features.py"),
                  encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("poi_id", src)
        renamed = copy.deepcopy(self.a)
        renamed["poi_id"] = "ghost-id"
        renamed["name"] = "Ghost"
        self.assertEqual(extract(self.a, self.b), extract(renamed, self.b))

    def test_attr_deltas_antisymmetric(self):
        fwd, back = extract(self.a, self.b), extract(self.b, self.a)
        for i in range(4):  # group A
            self.assertAlmostEqual(fwd[i], -back[i], places=9)

    def test_cross_ordered_terms(self):
        fwd, back = extract(self.a, self.b), extract(self.b, self.a)
        for i in (4, 5, 6):  # meal_after, indoor_buffer, intensity_drop
            self.assertAlmostEqual(fwd[i], -back[i], places=9)
        self.assertEqual(fwd[7], back[7])  # same_type symmetric (documented)

    def test_exposure_features_antisymmetric(self):
        fwd, back = extract(self.a, self.b), extract(self.b, self.a)
        for i in range(17, 21):  # outdoor, rain_cover, sun, wind
            self.assertAlmostEqual(fwd[i], -back[i], places=9)

    def test_exposure_features_read_smart_tags(self):
        a = {"type": "beach", "smart_tags": {
            "outdoor_exposure": 0.95, "sun_exposure": 0.9,
            "wind_exposure": 0.9, "rain_cover": "open"}}
        b = {"type": "museum", "smart_tags": {
            "outdoor_exposure": 0.05, "sun_exposure": 0.05,
            "wind_exposure": 0.05, "rain_cover": "enclosed"}}
        fwd, back = extract(a, b), extract(b, a)
        i_out = FEATURE_NAMES.index("x_outdoor_exposure")
        i_rain = FEATURE_NAMES.index("x_rain_cover")
        i_sun = FEATURE_NAMES.index("x_sun_exposure")
        i_wind = FEATURE_NAMES.index("x_wind_exposure")
        self.assertAlmostEqual(fwd[i_out], 0.9, places=6)
        self.assertAlmostEqual(fwd[i_rain], 1.0, places=6)  # open both ends
        self.assertAlmostEqual(fwd[i_sun], 0.85, places=6)
        self.assertAlmostEqual(fwd[i_wind], 0.85, places=6)

    def test_exposure_type_fallback_without_smart_tags(self):
        a, b = {"type": "beach"}, {"type": "museum"}
        self.assertGreater(
            extract(a, b)[FEATURE_NAMES.index("x_outdoor_exposure")], 0.5)
        # Unknown/absent type maps to the neutral 0.5, never a crash.
        c = {"type": "unmapped-category"}
        self.assertEqual(extract(a, c)[FEATURE_NAMES.index("x_rain_cover")],
                         0.5)

    def test_neutral_defaults(self):
        self.assertEqual(extract(self.a, self.b),
                         extract(self.a, self.b, user={}, ctx={}))
        vec = extract(self.a, self.b)
        self.assertEqual(vec[8:11], [0.0, 0.0, 0.0])  # centered user
        self.assertEqual(vec[11], 0.0)


if __name__ == "__main__":
    unittest.main()
