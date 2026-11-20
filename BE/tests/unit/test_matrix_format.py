"""dense_v1 matrix format: same cells as legacy, legacy read API unchanged."""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)

from BE.common import load_matrix_cells  # noqa: E402
from BE.matrix_format import DENSE, DenseCells, cells_of, to_dense  # noqa: E402

LEGACY = {"ids": ["a", "b", "c"], "source": "osrm", "cells": {
    "a->a": {"km": 0.0, "minutes": 0}, "a->b": {"km": 1.24, "minutes": 4}, "a->c": {"km": 3.0, "minutes": 9},
    "b->a": {"km": 1.3, "minutes": 5}, "b->b": {"km": 0.0, "minutes": 0},
    "c->a": {"km": 3.1, "minutes": 8}, "c->b": {"km": 2.0, "minutes": 6}, "c->c": {"km": 0.0, "minutes": 0}}}


class TestDense(unittest.TestCase):
    def test_round_trip_and_missing_cell_stays_missing(self):
        d = to_dense(LEGACY)
        self.assertEqual(d["format"], DENSE)
        self.assertNotIn("cells", d)
        cells = cells_of(d)
        self.assertEqual(cells["a->b"], {"km": 1.2, "minutes": 4})
        self.assertNotIn("b->c", cells)              # unroutable: absent, never 0
        self.assertIsNone(cells.get("b->c"))
        self.assertIsNone(cells.get("x->a"))
        self.assertEqual(len(cells), 8)
        self.assertEqual(set(cells), set(LEGACY["cells"]))
        self.assertEqual(cells.row_ids, ["a", "b", "c"])

    def test_legacy_passes_through(self):
        self.assertIs(cells_of(LEGACY), LEGACY["cells"])

    def test_mixed_sources_refused(self):
        doc = {**LEGACY, "cells": {**LEGACY["cells"], "a->b": {"km": 1, "minutes": 4, "source": "haversine_seed"}}}
        with self.assertRaises(ValueError):
            to_dense(doc)

    def test_size_mismatch_refused(self):
        with self.assertRaises(ValueError):
            DenseCells(["a", "b"], [0, 1, 2], [0.0, 1.0, 2.0])


class TestSnapshotMatrix(unittest.TestCase):
    def test_v2_matrix_is_dense_and_complete(self):
        cells = load_matrix_cells(os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2"))
        self.assertIsInstance(cells, DenseCells)
        self.assertEqual(len(cells), cells.n * cells.n)


if __name__ == "__main__":
    unittest.main()
