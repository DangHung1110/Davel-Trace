"""Unit test for matrix service (T010). Fixture-based, no lane-A files.

Run from repo root: python BE/tests/unit/test_matrix.py -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.matrix import MatrixMissError, MatrixService  # noqa: E402


def make_snapshot(tmp: str) -> str:
    snap = os.path.join(tmp, "snap")
    os.makedirs(snap)
    ids = ["a", "b", "c"]
    cells = {}
    mins = {("a", "b"): 10, ("b", "a"): 10, ("a", "c"): 25,
            ("c", "a"): 25, ("b", "c"): 12, ("c", "b"): 12}
    for x in ids:
        for y in ids:
            cells[f"{x}->{y}"] = {"km": 1.0,
                                  "minutes": 0 if x == y else mins[(x, y)]}
    with open(os.path.join(snap, "matrix.json"), "w", encoding="utf-8") as f:
        json.dump({"ids": ids, "cells": cells, "source": "cache"}, f)
    return snap


class TestMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = MatrixService(make_snapshot(tempfile.mkdtemp(prefix="mx_")))

    def test_cache_hit(self):
        self.assertEqual(self.svc.minutes("a", "b"), (10, "cache"))

    def test_diagonal_zero(self):
        self.assertEqual(self.svc.minutes("a", "a"), (0, "cache"))

    def test_miss_raises_never_guesses(self):
        with self.assertRaises(MatrixMissError):
            self.svc.minutes("a", "ghost")
        with open(os.path.join("BE", "app", "services", "matrix.py"),
                   encoding="utf-8") as f:
            src = f.read()
        for marker in ("6371", "radians", "asin(", "math.sin", "acos("):
            self.assertNotIn(marker, src)

    def test_travel_fit(self):
        self.assertTrue(self.svc.travel_fit("a", "b", 15))
        self.assertFalse(self.svc.travel_fit("a", "c", 20))

    def test_osrm_hook_disabled_offline(self):
        with self.assertRaises((MatrixMissError, RuntimeError)):
            MatrixService(self.svc.snapshot_dir,
                          osrm_base_url="http://router.example").minutes("a", "ghost")


if __name__ == "__main__":
    unittest.main()
