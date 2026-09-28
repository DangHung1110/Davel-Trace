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

    def test_16_features_unique_names(self):
        self.assertEqual(N_FEATURES, 16)
        self.assertEqual(len(set(FEATURE_NAMES)), 16)
        self.assertEqual(len(extract(self.a, self.b)), 16)

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

    def test_neutral_defaults(self):
        self.assertEqual(extract(self.a, self.b),
                         extract(self.a, self.b, user={}, ctx={}))
        vec = extract(self.a, self.b)
        self.assertEqual(vec[8:11], [0.0, 0.0, 0.0])  # centered user
        self.assertEqual(vec[11], 0.0)


if __name__ == "__main__":
    unittest.main()
