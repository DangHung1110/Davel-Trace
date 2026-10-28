"""Unit test for the append-only matrix expansion (T010b follow-up).

No Docker, no network: the OSRM client is faked. Asserts the expansion only
appends verified POIs, never rewrites an existing cell, keeps B3 holes absent,
and records what was added (categories + fetch source) on the artifact.

Run from repo root: python BE/tests/unit/test_expand_poi_matrix.py -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.matrix import MatrixService  # noqa: E402
from BE.tools import expand_poi_matrix as epm  # noqa: E402

POIS = [
    {"poi_id": "a", "name": "Alpha", "cat": "restaurant", "verified": True,
     "lat": 16.00, "lon": 108.00},
    {"poi_id": "b", "name": "Beta", "cat": "restaurant", "verified": True,
     "lat": 16.05, "lon": 108.05},
    {"poi_id": "c", "name": "Chua", "cat": "attraction", "verified": True,
     "lat": 16.10, "lon": 108.10},
    {"poi_id": "d", "name": "Bai bien", "cat": "beach", "verified": True,
     "lat": 16.15, "lon": 108.15},
    {"poi_id": "u", "name": "Unverified", "cat": "museum", "verified": False,
     "lat": 16.20, "lon": 108.20},
    {"poi_id": "n", "name": "NoCoords", "cat": "park", "verified": True},
]

EXISTING_IDS = ["a", "b"]


def existing_doc() -> dict:
    cells = {}
    for i, a in enumerate(EXISTING_IDS):
        for j, b in enumerate(EXISTING_IDS):
            cells[f"{a}->{b}"] = {"km": 0.0 if a == b else 9.99,
                                  "minutes": 0 if a == b else 99}
    return {
        "snapshot": "danang-v1", "ids": list(EXISTING_IDS), "n": 2,
        "source": "osrm", "confidence": "high",
        "osrm_base_url": "http://127.0.0.1:5000",
        "coverage": {"pairs_total": 4, "cells": 4, "osrm": 4,
                     "haversine_seed": 0, "infeasible": 0},
        "stats": {"requests": 1, "failed_requests": 0, "failed_shards": [],
                  "last_error": None, "elapsed_s": 0.5},
        "cells": cells,
    }


class FakeClient:
    def __init__(self, holes=()):
        self.holes = set(holes)
        self.points = []

    def table(self, points):
        self.points = [p[0] for p in points]
        cells = {}
        for i, (a, _la, _lo) in enumerate(points):
            for j, (b, _lb, _lob) in enumerate(points):
                if (a, b) in self.holes:
                    continue
                cells[(a, b)] = {"km": 0.0 if i == j else 1.23,
                                 "minutes": 0 if i == j else 5 + abs(i - j),
                                 "source": "osrm"}
        return cells, {"requests": 1, "failed_requests": 0,
                       "failed_shards": [], "last_error": None,
                       "elapsed_s": 0.01, "cells": len(cells)}


class TestSelection(unittest.TestCase):
    def test_only_verified_with_coords_not_already_present(self):
        picked = epm.select_expansion(POIS, EXISTING_IDS)
        self.assertEqual([p["poi_id"] for p in picked], ["c", "d"])

    def test_include_unverified_is_opt_in(self):
        picked = epm.select_expansion(POIS, EXISTING_IDS, verified_only=False)
        self.assertEqual([p["poi_id"] for p in picked], ["c", "d", "u"])

    def test_category_counts(self):
        self.assertEqual(epm.category_counts(POIS),
                         {"attraction": 1, "beach": 1, "museum": 1,
                          "park": 1, "restaurant": 2})


class TestMerge(unittest.TestCase):
    def test_append_only_keeps_old_cells_and_adds_new_pairs(self):
        old = existing_doc()
        snapshot = json.loads(json.dumps(old))  # deep copy for comparison
        picked = epm.select_expansion(POIS, EXISTING_IDS)
        cells, _ = FakeClient().table([("a", 0, 0), ("b", 0, 0),
                                       ("c", 0, 0), ("d", 0, 0)])
        doc, report = epm.merge(old, picked, cells,
                                osrm_url="http://127.0.0.1:5000",
                                elapsed_s=1.0, requests=1)
        self.assertEqual(doc["n"], 4)
        self.assertEqual(doc["ids"], ["a", "b", "c", "d"])
        for key, cell in snapshot["cells"].items():
            self.assertEqual(doc["cells"][key], cell)  # byte-identical
        self.assertEqual(report["added"], 4 * 4 - 2 * 2)  # new pairs only
        self.assertEqual(report["missing"], [])
        self.assertEqual(doc["coverage"],
                         {"pairs_total": 16, "cells": 16, "osrm": 16,
                          "haversine_seed": 0, "infeasible": 0})
        self.assertEqual(doc["cells"]["a->a"], {"km": 0.0, "minutes": 0})
        self.assertEqual(doc["stats"]["requests"], 2)
        self.assertEqual(doc["stats"]["elapsed_s"], 1.5)
        self.assertEqual(doc["expansions"][-1]["by_category"],
                         {"attraction": 1, "beach": 1})
        self.assertEqual(doc["expansions"][-1]["cells_added"], 12)

    def test_unroutable_new_pair_stays_absent(self):
        old = existing_doc()
        picked = epm.select_expansion(POIS, EXISTING_IDS)
        cells, _ = FakeClient(holes=[("c", "d")]).table(
            [("a", 0, 0), ("b", 0, 0), ("c", 0, 0), ("d", 0, 0)])
        doc, report = epm.merge(old, picked, cells,
                                osrm_url="http://127.0.0.1:5000",
                                elapsed_s=1.0)
        self.assertNotIn("c->d", doc["cells"])  # B3: never a silent 0
        self.assertEqual(report["missing"], ["c->d"])
        self.assertEqual(doc["coverage"]["infeasible"], 1)

    def test_duplicate_append_rejected(self):
        with self.assertRaises(ValueError):
            epm.merge(existing_doc(), [POIS[0]], {}, osrm_url="x", elapsed_s=0)

    def test_mixed_matrix_keeps_per_cell_source(self):
        old = existing_doc()
        old["cells"]["a->b"]["source"] = "haversine_seed"
        old["source"] = "mixed"
        picked = epm.select_expansion(POIS, EXISTING_IDS)
        cells, _ = FakeClient().table(
            [("a", 0, 0), ("b", 0, 0), ("c", 0, 0), ("d", 0, 0)])
        doc, _ = epm.merge(old, picked, cells, osrm_url="x", elapsed_s=0)
        self.assertEqual(doc["cells"]["a->b"]["source"], "haversine_seed")
        self.assertEqual(doc["coverage"]["haversine_seed"], 1)
        self.assertEqual(doc["coverage"]["osrm"], 15)


class TestMain(unittest.TestCase):
    def run_main(self, client):
        tmp = tempfile.mkdtemp(prefix="mxexp_")
        pois_path = os.path.join(tmp, "pois.json")
        matrix_path = os.path.join(tmp, "matrix.json")
        with open(pois_path, "w", encoding="utf-8") as f:
            json.dump({"snapshot": "danang-v1", "pois": POIS}, f)
        with open(matrix_path, "w", encoding="utf-8") as f:
            json.dump(existing_doc(), f)
        real = epm.OsrmClient
        epm.OsrmClient = lambda url, **kw: client
        try:
            code = epm.main(["--pois", pois_path, "--matrix", matrix_path,
                             "--backup", os.path.join(tmp, "backup.json")])
        finally:
            epm.OsrmClient = real
        return code, matrix_path, os.path.join(tmp, "backup.json")

    def test_main_merges_and_backs_up(self):
        code, matrix_path, backup = self.run_main(FakeClient())
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(backup))
        with open(matrix_path, encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(doc["n"], 4)
        svc = MatrixService(os.path.dirname(matrix_path))
        self.assertEqual(svc.ids, ["a", "b", "c", "d"])
        self.assertGreaterEqual(svc.minutes("a", "c")[0], 1)

    def test_main_returns_zero_when_nothing_to_add(self):
        code, matrix_path, _ = self.run_main(FakeClient())
        self.assertEqual(code, 0)
        # second run: every verified POI is already covered
        real = epm.OsrmClient
        epm.OsrmClient = lambda url, **kw: FakeClient()
        try:
            again = epm.main(["--pois", os.path.join(os.path.dirname(matrix_path), "pois.json"),
                              "--matrix", matrix_path,
                              "--backup", os.path.join(os.path.dirname(matrix_path), "b2.json")])
        finally:
            epm.OsrmClient = real
        self.assertEqual(again, 0)


if __name__ == "__main__":
    unittest.main()
