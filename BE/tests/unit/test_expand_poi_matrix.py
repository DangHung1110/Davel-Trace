"""Unit test for the append-only matrix expansion (T010b follow-up).

No Docker, no network: the OSRM client is faked. Asserts the expansion only
appends verified POIs, never rewrites an existing cell, keeps B3 holes absent,
and records what was added (categories + fetch source) on the artifact.

Run from repo root: python BE/tests/unit/test_expand_poi_matrix.py -v
"""

import contextlib
import io
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


class TestSelectBatch(unittest.TestCase):
    """--offset/--limit window the sorted selection deterministically (G5)."""

    def make_selection(self, n=305):
        pois = [{"poi_id": f"p{i:03d}", "name": f"Poi {i}", "cat": "restaurant",
                 "verified": True, "lat": 16.0, "lon": 108.0} for i in range(n)]
        return epm.select_expansion(pois, [])

    def test_defaults_keep_the_full_selection(self):
        full = self.make_selection()
        self.assertEqual([p["poi_id"] for p in epm.select_batch(full)],
                         [p["poi_id"] for p in full])
        self.assertEqual(epm.select_batch(full, 0, None), full)

    def test_batches_are_contiguous_slices_in_full_order(self):
        full = self.make_selection()
        ids = [p["poi_id"] for p in full]
        batch1 = epm.select_batch(full, 0, 100)
        batch2 = epm.select_batch(full, 100, 100)
        batch3 = epm.select_batch(full, 200, 105)
        self.assertEqual([p["poi_id"] for p in batch1], ids[0:100])
        self.assertEqual([p["poi_id"] for p in batch2], ids[100:200])
        self.assertEqual([p["poi_id"] for p in batch3], ids[200:305])
        self.assertEqual([p["poi_id"] for p in batch1 + batch2 + batch3], ids)

    def test_slice_is_deterministic_and_does_not_mutate(self):
        full = self.make_selection()
        before = [p["poi_id"] for p in full]
        first = [p["poi_id"] for p in epm.select_batch(full, 100, 50)]
        second = [p["poi_id"] for p in epm.select_batch(full, 100, 50)]
        self.assertEqual(first, second)
        self.assertEqual([p["poi_id"] for p in full], before)
        self.assertEqual(first, before[100:150])

    def test_offset_past_end_is_empty(self):
        full = self.make_selection(5)
        self.assertEqual(epm.select_batch(full, 10, 100), [])

    def test_negative_window_rejected(self):
        full = self.make_selection(3)
        with self.assertRaises(ValueError):
            epm.select_batch(full, -1, 10)
        with self.assertRaises(ValueError):
            epm.select_batch(full, 0, -1)


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


def batch_dataset(n_new=305):
    """One existing matrix POI (`base`) plus `n_new` verified candidates."""
    ids = ["base"]
    pois = [{"poi_id": "base", "name": "Base", "cat": "attraction",
             "verified": True, "lat": 16.0, "lon": 108.0}]
    for i in range(1, n_new + 1):
        pid = f"p{i:03d}"
        ids.append(pid)
        pois.append({"poi_id": pid, "name": f"Poi {i}", "cat": "restaurant",
                     "verified": True, "lat": 16.0 + i * 1e-4, "lon": 108.0})
    return pois, ids


def single_doc(ids=("base",)) -> dict:
    ids = list(ids)
    cells = {f"{a}->{b}": {"km": 0.0 if a == b else 1.0,
                           "minutes": 0 if a == b else 3}
             for a in ids for b in ids}
    return {
        "snapshot": "danang-v1", "ids": ids, "n": len(ids),
        "source": "osrm", "confidence": "high",
        "osrm_base_url": "http://127.0.0.1:5000",
        "coverage": {"pairs_total": len(ids) ** 2, "cells": len(cells),
                     "osrm": len(cells), "haversine_seed": 0, "infeasible": 0},
        "stats": {"requests": 1, "failed_requests": 0, "failed_shards": [],
                  "last_error": None, "elapsed_s": 0.5},
        "cells": cells,
    }


class TestMainBatching(unittest.TestCase):
    """G5: the over-cap guard must apply to the batch, not the full selection."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mxbatch_")
        self.pois, self.poi_ids = batch_dataset()
        self.pois_path = os.path.join(self.tmp, "pois.json")
        self.matrix_path = os.path.join(self.tmp, "matrix.json")
        with open(self.pois_path, "w", encoding="utf-8") as f:
            json.dump({"snapshot": "danang-v1", "pois": self.pois}, f)
        self.write_matrix(single_doc())

    def write_matrix(self, doc):
        with open(self.matrix_path, "w", encoding="utf-8") as f:
            json.dump(doc, f)

    def read_matrix(self):
        with open(self.matrix_path, encoding="utf-8") as f:
            return json.load(f)

    def run_main(self, argv, client=None):
        real = epm.OsrmClient
        epm.OsrmClient = lambda url, **kw: client or FakeClient()
        try:
            return epm.main(["--pois", self.pois_path, "--matrix", self.matrix_path,
                             "--backup", os.path.join(self.tmp, "b.json")] + argv)
        finally:
            epm.OsrmClient = real

    def test_no_flags_still_merges_the_whole_selection(self):
        # limit/offset default to the whole selection; over-cap "all" refuses.
        cap = epm.MAX_TABLE_SIZE
        pois, _ids = batch_dataset(cap)  # 1 existing + cap new > cap
        with open(self.pois_path, "w", encoding="utf-8") as f:
            json.dump({"snapshot": "danang-v1", "pois": pois}, f)
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.run_main([])
        self.assertEqual(code, 2)
        self.assertEqual(self.read_matrix()["ids"], ["base"])  # untouched

    def test_no_flags_merges_everything_when_under_the_cap(self):
        pois, ids = batch_dataset(50)
        with open(self.pois_path, "w", encoding="utf-8") as f:
            json.dump({"snapshot": "danang-v1", "pois": pois}, f)
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.run_main([])
        self.assertEqual(code, 0)
        self.assertEqual(self.read_matrix()["ids"], ids)

    def test_limit_merges_only_the_batch_in_sorted_order(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.run_main(["--limit", "100"])
        self.assertEqual(code, 0)
        doc = self.read_matrix()
        self.assertEqual(doc["ids"], ["base"] + [f"p{i:03d}" for i in range(1, 101)])
        self.assertEqual(doc["n"], 101)

    def test_offset_skips_after_sort(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.run_main(["--offset", "100", "--limit", "5"])
        self.assertEqual(code, 0)
        doc = self.read_matrix()
        self.assertEqual(doc["ids"],
                         ["base"] + [f"p{i:03d}" for i in range(101, 106)])

    def test_guard_triggers_on_batch_total(self):
        # 1 existing + cap new in one batch > cap.
        cap = epm.MAX_TABLE_SIZE
        pois, _ids = batch_dataset(cap)
        with open(self.pois_path, "w", encoding="utf-8") as f:
            json.dump({"snapshot": "danang-v1", "pois": pois}, f)
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.run_main(["--limit", str(cap)])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "b.json")))
        self.assertEqual(self.read_matrix()["ids"], ["base"])

    def test_guard_allows_batch_exactly_at_the_cap(self):
        # 1 existing + (cap - 1) new == cap.
        cap = epm.MAX_TABLE_SIZE
        pois, _ids = batch_dataset(cap - 1)
        with open(self.pois_path, "w", encoding="utf-8") as f:
            json.dump({"snapshot": "danang-v1", "pois": pois}, f)
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.run_main(["--limit", str(cap - 1)])
        self.assertEqual(code, 0)
        self.assertEqual(self.read_matrix()["n"], cap)

    def test_three_batches_cover_the_selection_while_under_the_cap(self):
        pois, ids = batch_dataset(290)  # 1 existing + 290 = 291 <= 300
        with open(self.pois_path, "w", encoding="utf-8") as f:
            json.dump({"snapshot": "danang-v1", "pois": pois}, f)
        for limit in ("100", "100", "90"):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.run_main(["--limit", limit,
                                                "--offset", "0"]), 0)
        doc = self.read_matrix()
        self.assertEqual(doc["ids"], ids)  # 1 existing + 290 new, sorted order
        self.assertEqual(doc["n"], 291)

    def test_batch_that_would_exceed_the_cap_is_refused(self):
        # 101 existing + cap new in one batch > cap, refuse.
        cap = epm.MAX_TABLE_SIZE
        doc = self.read_matrix()
        doc["ids"] = ["base"] + [f"p{i:03d}" for i in range(1, 101)]
        doc["n"] = len(doc["ids"])
        self.write_matrix(doc)
        pois, _ids = batch_dataset(cap)  # p001..p600; p001..p100 already covered
        with open(self.pois_path, "w", encoding="utf-8") as f:
            json.dump({"snapshot": "danang-v1", "pois": pois}, f)
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.run_main(["--limit", str(cap)])
        self.assertEqual(code, 2)

    def test_dry_run_prints_the_batch_slice_only(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.run_main(["--dry-run", "--offset", "100", "--limit", "3"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("offset=100", text)
        self.assertIn("305", text)  # full selection size still reported
        for pid in ("p101", "p102", "p103"):
            self.assertIn(pid, text)
        for pid in ("p100", "p104"):
            self.assertNotIn(pid, text)
        self.assertEqual(self.read_matrix()["ids"], ["base"])  # never writes

    def test_dry_run_batch_matches_the_merge(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.run_main(["--dry-run", "--limit", "10"])
        selection = epm.select_expansion(self.pois, self.read_matrix()["ids"])
        expected = [p["poi_id"] for p in epm.select_batch(selection, 0, 10)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.run_main(["--limit", "10"])
        merged = [pid for pid in self.read_matrix()["ids"] if pid != "base"]
        self.assertEqual(merged, expected)
        self.assertEqual(len(merged), 10)



if __name__ == "__main__":
    unittest.main()
