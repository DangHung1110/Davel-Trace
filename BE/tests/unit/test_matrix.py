"""Unit test for matrix service (T010) + OSRM backfill internals (T010b).

Fixture-based, no lane-A files, no Docker (OSRM client mocked). Keeps the
original T010 contract asserted: cache-first, per-cell/source labels, and a
miss is a loud error or (None, "infeasible") — never haversine, never 0.

Run from repo root: python BE/tests/unit/test_matrix.py -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.matrix import MatrixMissError, MatrixService  # noqa: E402
from BE.app.services.osrm_client import OsrmTableError  # noqa: E402


def make_snapshot(tmp: str, source: str = "cache", cell_source: str | None = None) -> str:
    snap = os.path.join(tmp, "snap")
    os.makedirs(snap, exist_ok=True)
    ids = ["a", "b", "c"]
    cells = {}
    mins = {("a", "b"): 10, ("b", "a"): 10, ("a", "c"): 25,
            ("c", "a"): 25, ("b", "c"): 12, ("c", "b"): 12}
    for x in ids:
        for y in ids:
            cell = {"km": 1.0, "minutes": 0 if x == y else mins[(x, y)]}
            if cell_source is not None:
                cell["source"] = cell_source
            cells[f"{x}->{y}"] = cell
    with open(os.path.join(snap, "matrix.json"), "w", encoding="utf-8") as f:
        json.dump({"ids": ids, "cells": cells, "source": source}, f)
    return snap


class FakeClient:
    """Stub OsrmClient: `table()` returns canned cells / raises / drops pairs."""

    def __init__(self, cells=None, error=None, drop=()):
        self.cells = cells or {}
        self.error = error
        self.drop = set(drop)
        self.calls = []

    def table(self, points):
        self.calls.append([p[0] for p in points])
        if self.error is not None:
            raise self.error
        out = {}
        for (a, b) in self.cells:
            if (a, b) in self.drop:
                continue
            out[(a, b)] = self.cells[(a, b)]
        return out, {"requests": 1, "failed_requests": 0, "missing": len(self.drop)}


OSRM_CELLS = {
    ("a", "ghost"): {"km": 3.5, "minutes": 9, "source": "osrm"},
    ("ghost", "a"): {"km": 3.5, "minutes": 9, "source": "osrm"},
}


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

    # -- T010b: per-cell source labels --------------------------------------

    def test_per_cell_source_overrides_file_source(self):
        svc = MatrixService(make_snapshot(tempfile.mkdtemp(prefix="mx_"),
                                          source="mixed", cell_source="haversine_seed"))
        self.assertEqual(svc.minutes("a", "b"), (10, "haversine_seed"))

    def test_file_source_fallback_when_cell_has_none(self):
        svc = MatrixService(make_snapshot(tempfile.mkdtemp(prefix="mx_"), source="osrm"))
        self.assertEqual(svc.minutes("a", "b"), (10, "osrm"))

    def test_minutes_or_none_infeasible_not_zero(self):
        self.assertEqual(self.svc.minutes_or_none("a", "ghost"), (None, "infeasible"))
        self.assertEqual(self.svc.minutes_or_none("a", "b"), (10, "cache"))

    # -- T010b: OSRM backfill on cache miss ---------------------------------

    def test_backfill_returns_osrm_label_and_caches(self):
        client = FakeClient(cells=OSRM_CELLS)
        svc = MatrixService(self.svc.snapshot_dir, osrm_base_url="http://r:5000",
                            coords={"a": (16.0, 108.0), "ghost": (16.1, 108.1)},
                            osrm_client=client)
        self.assertEqual(svc.minutes("a", "ghost"), (9, "osrm"))
        self.assertEqual(svc.minutes("a", "ghost"), (9, "osrm"))  # cached now
        self.assertEqual(len(client.calls), 1)

    def test_backfill_unroutable_pair_is_infeasible(self):
        client = FakeClient(cells=OSRM_CELLS, drop=[("a", "ghost")])
        svc = MatrixService(self.svc.snapshot_dir, osrm_base_url="http://r:5000",
                            coords={"a": (16.0, 108.0), "ghost": (16.1, 108.1)},
                            osrm_client=client)
        with self.assertRaises(MatrixMissError):
            svc.minutes("a", "ghost")
        self.assertEqual(svc.minutes_or_none("a", "ghost"), (None, "infeasible"))
        self.assertNotEqual(svc.minutes_or_none("a", "ghost")[0], 0)

    def test_backfill_network_failure_raises_miss(self):
        client = FakeClient(error=OsrmTableError("connection refused"))
        svc = MatrixService(self.svc.snapshot_dir, osrm_base_url="http://r:5000",
                            coords={"a": (16.0, 108.0), "ghost": (16.1, 108.1)},
                            osrm_client=client)
        with self.assertRaises(MatrixMissError):
            svc.minutes("a", "ghost")

    def test_backfill_needs_coords_when_url_set(self):
        svc = MatrixService(self.svc.snapshot_dir, osrm_base_url="http://r:5000")
        with self.assertRaises(RuntimeError):
            svc.minutes("a", "ghost")
        self.assertEqual(svc.minutes_or_none("a", "ghost"), (None, "infeasible"))


if __name__ == "__main__":
    unittest.main()
