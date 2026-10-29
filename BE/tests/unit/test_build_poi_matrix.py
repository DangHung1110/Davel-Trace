"""Unit test for the top-N OSRM matrix builder (T010b). No Docker, no network.

Asserts: top-N selection by rating, strict B3 output (holes omitted, never 0),
labelled haversine fallback (`--seed-fallback`), coverage counts, and that the
produced file round-trips through `MatrixService`.

Run from repo root: python BE/tests/unit/test_build_poi_matrix.py -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.matrix import MatrixMissError, MatrixService  # noqa: E402
from BE.tools import build_poi_matrix as bpm  # noqa: E402

POIS = [
    {"poi_id": "a", "name": "Alpha", "rating": 4.9, "lat": 16.00, "lon": 108.00},
    {"poi_id": "b", "name": "Beta", "rating": 4.9, "lat": 16.05, "lon": 108.05},
    {"poi_id": "c", "name": "Gamma", "rating": 4.5, "lat": 16.10, "lon": 108.10},
    {"poi_id": "d", "name": "Delta", "rating": None, "lat": 16.15, "lon": 108.15},
    {"poi_id": "e", "name": "NoCoords", "rating": 5.0},
]


class FakeClient:
    def __init__(self, holes=(), zero_cells=False):
        self.holes = set(holes)
        self.zero_cells = zero_cells
        self.calls = []

    def table(self, points):
        self.calls.append([p[0] for p in points])
        cells = {}
        if not self.zero_cells:
            for i, (a, _la, _lo) in enumerate(points):
                for j, (b, _lb, _lob) in enumerate(points):
                    if (a, b) in self.holes:
                        continue
                    cells[(a, b)] = {"km": 0.0 if i == j else 1.23,
                                     "minutes": 0 if i == j else 5 + abs(i - j),
                                     "source": "osrm"}
        return cells, {"requests": 1, "failed_requests": 0, "failed_shards": [],
                       "last_error": None, "elapsed_s": 0.001,
                       "missing": len(self.holes), "cells": len(cells),
                       "missing_pairs": [list(h) for h in self.holes]}


class TestSelection(unittest.TestCase):
    def test_top_by_rating_tiebreak_poi_id(self):
        picked = bpm.select_top(POIS, 3)
        self.assertEqual([p["poi_id"] for p in picked], ["a", "b", "c"])

    def test_skips_pois_without_coords(self):
        picked = bpm.select_top(POIS, 10)
        self.assertNotIn("e", [p["poi_id"] for p in picked])
        self.assertEqual(len(picked), 4)

    def test_duplicate_ids_rejected(self):
        dup = POIS[:2] + [dict(POIS[0])]
        with self.assertRaises(ValueError):
            bpm.select_top(dup, 3)


class TestBuild(unittest.TestCase):
    def test_strict_full_coverage_has_no_per_cell_source(self):
        picked = bpm.select_top(POIS, 3)
        doc = bpm.build(picked, client=FakeClient(), snapshot="danang-v1")
        self.assertEqual(doc["source"], "osrm")
        self.assertEqual(doc["confidence"], "high")
        self.assertEqual(doc["coverage"],
                         {"pairs_total": 9, "cells": 9, "osrm": 9,
                          "haversine_seed": 0, "infeasible": 0})
        self.assertEqual(len(doc["cells"]), 9)
        for cell in doc["cells"].values():
            self.assertNotIn("source", cell)  # file-level source is enough
        self.assertEqual(doc["cells"]["a->a"], {"km": 0.0, "minutes": 0})
        diag = [c for k, c in doc["cells"].items() if k.split("->")[0] == k.split("->")[1]]
        for cell in diag:
            self.assertEqual(cell["minutes"], 0)

    def test_strict_hole_is_infeasible_never_zero(self):
        picked = bpm.select_top(POIS, 3)
        doc = bpm.build(picked, client=FakeClient(holes=[("a", "b")]),
                        snapshot="danang-v1")
        self.assertNotIn("a->b", doc["cells"])
        self.assertEqual(doc["coverage"]["pairs_total"], 9)
        self.assertEqual(doc["coverage"]["osrm"], 8)
        self.assertEqual(doc["coverage"]["infeasible"], 1)
        for key, cell in doc["cells"].items():
            a, b = key.split("->")
            if a != b:
                self.assertGreater(cell["minutes"], 0, key)  # never a silent 0

    def test_seed_fallback_fills_hole_labelled_haversine(self):
        picked = bpm.select_top(POIS, 3)
        doc = bpm.build(picked, client=FakeClient(holes=[("a", "b")]),
                        snapshot="danang-v1", seed_fallback=True)
        self.assertEqual(doc["source"], "mixed")
        self.assertEqual(doc["confidence"], "low")
        self.assertEqual(doc["coverage"],
                         {"pairs_total": 9, "cells": 9, "osrm": 8,
                          "haversine_seed": 1, "infeasible": 0})
        filled = doc["cells"]["a->b"]
        self.assertEqual(filled["source"], "haversine_seed")
        self.assertEqual(filled["confidence"], "low")
        self.assertGreaterEqual(filled["minutes"], 5)
        for cell in doc["cells"].values():
            self.assertIn(cell.get("source"), ("osrm", "haversine_seed"))

    def test_build_round_trips_through_matrix_service(self):
        picked = bpm.select_top(POIS, 3)
        tmp = tempfile.mkdtemp(prefix="mxb_")
        doc = bpm.build(picked, client=FakeClient(holes=[("a", "b")]),
                        snapshot="danang-v1")
        with open(os.path.join(tmp, "matrix.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f)
        svc = MatrixService(tmp)
        self.assertEqual(svc.minutes("a", "c"), (7, "osrm"))
        self.assertEqual(svc.minutes("a", "a"), (0, "cache"))
        with self.assertRaises(MatrixMissError):
            svc.minutes("a", "b")  # hole = infeasible, loud
        self.assertEqual(svc.minutes_or_none("a", "b"), (None, "infeasible"))


class TestMain(unittest.TestCase):
    def run_main(self, client, extra=()):
        tmp = tempfile.mkdtemp(prefix="mxm_")
        pois_path = os.path.join(tmp, "pois.json")
        out_path = os.path.join(tmp, "matrix.json")
        with open(pois_path, "w", encoding="utf-8") as f:
            json.dump({"snapshot": "danang-v1", "pois": POIS}, f)
        real = bpm.OsrmClient
        bpm.OsrmClient = lambda url, **kw: client
        try:
            code = bpm.main(["--pois", pois_path, "--out", out_path,
                             "--top", "3", *extra])
        finally:
            bpm.OsrmClient = real
        return code, out_path

    def test_main_writes_loadable_matrix(self):
        code, out = self.run_main(FakeClient())
        self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(doc["n"], 3)
        self.assertEqual(doc["coverage"]["infeasible"], 0)
        self.assertEqual(doc["snapshot"], os.path.basename(os.path.dirname(os.path.abspath(out))))

    def test_main_aborts_when_osrm_returns_nothing(self):
        code, out = self.run_main(FakeClient(zero_cells=True))
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(out))


class TestPhase3(unittest.TestCase):
    """--all, TooBig-safe chunking, honest metadata, dense output."""

    def test_select_all_keeps_snapshot_order_and_needs_coords(self):
        self.assertEqual([p["poi_id"] for p in bpm.select_all(POIS)],
                         ["a", "b", "c", "d"])
        with self.assertRaises(ValueError):
            bpm.select_all(POIS[:2] + [dict(POIS[0])])

    def test_safe_chunk_matches_osrm_toobig_rule(self):
        # Measured on osrm-routed v5.27.1 --max-table-size 300 with the 742
        # POIs: 121 sources OK (89,782 cells), 122 TooBig (90,524 > 300^2).
        self.assertEqual(bpm.safe_chunk(742, 300, 500), 121)
        self.assertEqual(bpm.safe_chunk(742, 300, 100), 100)
        self.assertEqual(bpm.safe_chunk(742, 1000, 742), 742)
        with self.assertRaises(ValueError):
            bpm.safe_chunk(100, 5, 10)  # 1 x 100 > 25

    def test_mode_only_claimed_from_osrm_meta(self):
        picked = bpm.select_top(POIS, 3)
        bare = bpm.build(picked, client=FakeClient(), snapshot="s")
        self.assertEqual(bare["mode"], "unspecified")
        meta = {"mode": "motorbike", "extract": "x.osm.pbf",
                "profile_sha256": "abc"}
        doc = bpm.build(picked, client=FakeClient(), snapshot="s",
                        osrm_meta=meta, top_by="all")
        self.assertEqual((doc["mode"], doc["extract"], doc["top_by"]),
                         ("motorbike", "x.osm.pbf", "all"))
        self.assertEqual(doc["osrm"], meta)

    def test_main_all_writes_dense_and_round_trips(self):
        tmp = tempfile.mkdtemp(prefix="mx3_")
        meta_path = os.path.join(tmp, "osrm-meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"mode": "motorbike"}, f)
        code, out = TestMain().run_main(
            FakeClient(holes=[("a", "b")]),
            extra=("--all", "--osrm-meta", meta_path, "--min-coverage", "0.9"))
        self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as f:
            raw = json.load(f)
        self.assertEqual(raw["format"], "dense-v1")
        self.assertEqual(raw["ids"], ["a", "b", "c", "d"])
        self.assertIsNone(raw["minutes"][0][1])  # hole stays a hole (B3)
        self.assertEqual(raw["mode"], "motorbike")
        svc = MatrixService(os.path.dirname(out))
        self.assertEqual(svc.minutes("a", "c"), (7, "osrm"))
        self.assertEqual(svc.minutes_or_none("a", "b"), (None, "infeasible"))

    def test_seed_fallback_falls_back_to_legacy_format(self):
        code, out = TestMain().run_main(
            FakeClient(holes=[("a", "b")]), extra=("--seed-fallback",))
        self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as f:
            raw = json.load(f)
        self.assertNotIn("format", raw)
        self.assertEqual(raw["cells"]["a->b"]["source"], "haversine_seed")


class TestSeedCell(unittest.TestCase):
    def test_seed_cell_matches_legacy_formula(self):
        cell = bpm.seed_cell(16.0, 108.0, 16.0, 108.1)
        km = bpm.haversine_km(16.0, 108.0, 16.0, 108.1)
        self.assertAlmostEqual(km, 10.66, delta=0.05)
        self.assertEqual(cell["minutes"], 21)  # 10.66 km / 30 kmh
        self.assertEqual(cell["source"], "haversine_seed")

    def test_seed_cell_floor_five_minutes(self):
        cell = bpm.seed_cell(16.0, 108.0, 16.0002, 108.0002)
        self.assertEqual(cell["minutes"], 5)


if __name__ == "__main__":
    unittest.main()
