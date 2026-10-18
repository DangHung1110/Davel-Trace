"""Integrity test for the committed OSRM matrix snapshot (T010b, lane B).

Guards `BE/data/snapshots/danang-v1/matrix.json` — the top-150 (by rating)
OSRM `/table` artifact built by `BE/tools/build_poi_matrix.py` from lane A's
snapshot POIs. No Docker, no network: file checks + a `MatrixService`
round-trip only. Skips when the artifact is absent so unit runs stay green in
fresh checkouts where the snapshot has not been built yet.

Run from repo root: python BE/tests/unit/test_matrix_snapshot.py -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.matrix import MatrixService  # noqa: E402
from BE.app.services.osrm_client import OsrmClient  # noqa: E402

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MATRIX = os.path.join(_REPO_ROOT, "BE", "data", "snapshots", "danang-v1", "matrix.json")
N_TOP = 150


@unittest.skipUnless(os.path.exists(MATRIX), "matrix snapshot not built")
class TestMatrixSnapshotArtifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MATRIX, encoding="utf-8") as f:
            cls.doc = json.load(f)

    def test_full_coverage_n_by_n(self):
        doc = self.doc
        self.assertEqual(doc["n"], N_TOP)
        self.assertEqual(len(doc["ids"]), N_TOP)
        self.assertEqual(len(set(doc["ids"])), N_TOP, "ids must be unique")
        cov = doc["coverage"]
        self.assertEqual(cov["pairs_total"], N_TOP * N_TOP)
        self.assertEqual(cov["cells"], len(doc["cells"]))
        self.assertEqual(cov["infeasible"], 0)  # every pair routable in bbox
        self.assertEqual(doc["snapshot"], "danang-v1")

    def test_osrm_labelled_and_never_silent_zero(self):
        doc = self.doc
        self.assertEqual(doc["source"], "osrm")
        self.assertEqual(doc["confidence"], "high")
        for key, cell in doc["cells"].items():
            a, b = key.split("->")
            self.assertNotIn("source", cell)  # file-level source is enough
            if a == b:
                self.assertEqual(cell, {"km": 0.0, "minutes": 0}, key)
            else:
                self.assertGreaterEqual(cell["minutes"], 1, key)
                self.assertGreater(cell["km"], 0.0, key)

    def test_service_reads_artifact(self):
        svc = MatrixService(os.path.dirname(MATRIX))
        self.assertEqual(len(svc.ids), N_TOP)
        a, b = self.doc["ids"][0], self.doc["ids"][1]
        self.assertEqual(svc.minutes(a, a), (0, "cache"))
        minutes, source = svc.minutes(a, b)
        self.assertGreaterEqual(minutes, 1)
        self.assertEqual(source, "osrm")
        self.assertEqual(svc.minutes_or_none(a, b)[1], "osrm")

    def test_backfill_wiring_matches_artifact(self):
        # The artifact was built for the documented local service; wiring the
        # client at that URL must be possible without network access.
        client = OsrmClient(self.doc["osrm_base_url"])
        self.assertEqual(client.base_url, "http://127.0.0.1:5000")
        self.assertGreaterEqual(client.chunk, 1)


if __name__ == "__main__":
    unittest.main()
