"""dense-v1 matrix format + cached loader (Phase 3). No snapshot, no network.

- DenseCells is a read-only "a->b" Mapping: a null cell is ABSENT (B3), the
  diagonal and real cells read back exactly, len/iter skip holes;
- dense_document refuses per-cell non-OSRM sources (keep legacy for those);
- load_matrix_doc serves both formats, parses once per file version and
  rejects unknown formats; every consumer seam reads the dense file.

Run from repo root: python -m pytest BE/tests/unit/test_matrix_dense.py -q
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE import common  # noqa: E402
from BE.app.routers import evaluate as evaluate_router  # noqa: E402
from BE.app.services import matrix as matrix_mod  # noqa: E402
from BE.app.services import snapshot  # noqa: E402
from BE.app.services.matrix import (  # noqa: E402
    DENSE_FORMAT, DenseCells, MatrixService, dense_document, load_cells,
    load_matrix_doc)

IDS = ["a", "b", "c"]
MINUTES = [[0, 5, None], [6, 0, 7], [8, 9, 0]]
KM = [[0.0, 1.5, None], [1.6, 0.0, 2.1], [2.4, 2.7, 0.0]]


def _write(directory, doc):
    path = os.path.join(directory, "matrix.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return path


def _dense_doc():
    return {"format": DENSE_FORMAT, "snapshot": "t", "ids": IDS, "n": 3,
            "source": "osrm", "minutes": MINUTES, "km": KM}


class TestDenseCells(unittest.TestCase):
    def setUp(self):
        self.cells = DenseCells(IDS, MINUTES, KM)

    def test_reads_cells_and_diagonal(self):
        self.assertEqual(self.cells["a->b"], {"km": 1.5, "minutes": 5})
        self.assertEqual(self.cells.get("b->c"), {"km": 2.1, "minutes": 7})
        self.assertEqual(self.cells["c->c"], {"km": 0.0, "minutes": 0})

    def test_null_cell_is_absent_never_zero(self):
        self.assertIsNone(self.cells.get("a->c"))
        self.assertNotIn("a->c", self.cells)
        with self.assertRaises(KeyError):
            self.cells["a->c"]

    def test_unknown_ids_and_bad_keys_are_absent(self):
        for key in ("a->z", "z->a", "ab", "", ("a", "b")):
            self.assertNotIn(key, self.cells)
        self.assertEqual(self.cells.get("x->y", "miss"), "miss")

    def test_len_and_iter_skip_holes(self):
        self.assertEqual(len(self.cells), 8)
        self.assertEqual(len(list(self.cells)), 8)
        self.assertNotIn("a->c", set(self.cells))
        self.assertEqual(dict(self.cells)["c->b"], {"km": 2.7, "minutes": 9})

    def test_row_count_must_match_ids(self):
        with self.assertRaises(ValueError):
            DenseCells(IDS, MINUTES[:2], KM)


class TestDenseDocument(unittest.TestCase):
    def test_round_trip_from_tuple_or_string_keys(self):
        cells = {("a", "a"): {"km": 0.0, "minutes": 0},
                 ("a", "b"): {"km": 1.234, "minutes": 5, "source": "osrm"},
                 "b->a": {"km": 1.6, "minutes": 6}}
        doc = dense_document(["a", "b"], cells, {"snapshot": "t"})
        self.assertEqual(doc["format"], DENSE_FORMAT)
        self.assertEqual(doc["minutes"], [[0, 5], [6, None]])
        self.assertEqual(doc["km"], [[0.0, 1.23], [1.6, None]])
        self.assertEqual((doc["snapshot"], doc["n"]), ("t", 2))

    def test_seeded_cells_must_stay_legacy(self):
        cells = {("a", "b"): {"km": 1.0, "minutes": 5,
                              "source": "haversine_seed"}}
        with self.assertRaises(ValueError):
            dense_document(["a", "b"], cells, {})


class TestLoader(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mxd_")
        matrix_mod._DOC_CACHE.clear()

    def test_dense_and_legacy_read_the_same(self):
        dense = load_matrix_doc(_write(self.dir, _dense_doc()))
        legacy_dir = tempfile.mkdtemp(prefix="mxl_")
        legacy = load_matrix_doc(_write(legacy_dir, {
            "ids": IDS, "cells": dict(DenseCells(IDS, MINUTES, KM))}))
        self.assertEqual(dict(dense["cells"]), dict(legacy["cells"]))
        self.assertNotIn("minutes", dense)  # moved into the cells view

    def test_parsed_once_per_file_version(self):
        path = _write(self.dir, _dense_doc())
        with mock.patch.object(matrix_mod.json, "load",
                               wraps=json.load) as parse:
            first = load_matrix_doc(path)
            second = load_matrix_doc(path)
            self.assertIs(first, second)
            self.assertEqual(parse.call_count, 1)
            doc = _dense_doc()
            doc["minutes"] = [[0, 50, None], [6, 0, 7], [8, 9, 0]]
            _write(self.dir, doc)
            os.utime(path, ns=(1, 1))  # new mtime even on a coarse clock
            self.assertEqual(load_matrix_doc(path)["cells"]["a->b"]["minutes"], 50)
            self.assertEqual(parse.call_count, 2)

    def test_unknown_format_is_loud(self):
        with self.assertRaises(ValueError):
            load_matrix_doc(_write(self.dir, {"format": "sparse-v9", "ids": []}))

    def test_missing_matrix_is_empty_for_load_cells(self):
        self.assertEqual(load_cells(os.path.join(self.dir, "nope")), {})


class TestConsumersReadDense(unittest.TestCase):
    """Every seam that used to json.load(...)["cells"] now reads dense too."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="mxc_")
        _write(cls.dir, _dense_doc())
        with open(os.path.join(cls.dir, "pois.json"), "w", encoding="utf-8") as f:
            json.dump({"pois": [{"poi_id": pid} for pid in IDS]}, f)

    def test_matrix_service(self):
        svc = MatrixService(self.dir)
        self.assertEqual(svc.minutes("a", "b"), (5, "osrm"))
        self.assertEqual(svc.minutes_or_none("a", "c"), (None, "infeasible"))

    def test_common_and_evaluate_router(self):
        self.assertEqual(common.load_matrix_cells(self.dir)["b->c"]["minutes"], 7)
        _pois, cells = evaluate_router.load_eval_context(self.dir)
        self.assertEqual(cells["c->a"]["minutes"], 8)

    def test_snapshot_validator_sees_the_hole(self):
        with self.assertRaises(ValueError) as ctx:
            snapshot.load_matrix(self.dir, IDS)
        self.assertIn("a->c", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
