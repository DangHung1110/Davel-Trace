"""danang-v2 matrix is stored in main's dense-v1 format and covers every active POI."""

import json
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)

from BE.app.services.matrix import DENSE_FORMAT, load_matrix_doc  # noqa: E402

SNAP = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")


class TestV2Matrix(unittest.TestCase):
    def test_dense_complete_and_covers_active(self):
        doc = load_matrix_doc(os.path.join(SNAP, "matrix.json"))
        self.assertEqual(doc["format"], DENSE_FORMAT)
        cells = doc["cells"]
        self.assertEqual(len(cells), doc["n"] * doc["n"])
        self.assertEqual(set(cells.row_ids), set(doc["ids"]))
        with open(os.path.join(SNAP, "pois.json"), encoding="utf-8") as f:
            active = [p["poi_id"] for p in json.load(f)["pois"] if p["status"] == "active"]
        self.assertEqual([p for p in active if p not in set(doc["ids"])], [])
        a = doc["ids"][0]
        self.assertEqual(cells.get(f"{a}->{a}")["minutes"], 0)


if __name__ == "__main__":
    unittest.main()
