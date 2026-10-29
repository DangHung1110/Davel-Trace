"""Integrity test for the committed OSRM matrix snapshot (T010b, lane B).

Guards `BE/data/snapshots/danang-v1/matrix.json` — the OSRM `/table` artifact
built by `BE/tools/build_poi_matrix.py` (top-150 by rating) and APPENDED to by
`BE/tools/expand_poi_matrix.py` (every verified POI the top-150 missed, so the
optimizer has non-food categories to balance a day). No Docker, no network:
file checks + a `MatrixService` round-trip only. Skips when the artifact is
absent so unit runs stay green in fresh checkouts where the snapshot has not
been built yet.

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
SNAPSHOT_DIR = os.path.join(_REPO_ROOT, "BE", "data", "snapshots", "danang-v1")
MATRIX = os.path.join(SNAPSHOT_DIR, "matrix.json")
POIS = os.path.join(SNAPSHOT_DIR, "pois.json")
N_TOP = 150  # original top-N build; the expansion only appends
SIGHTSEEING = {"attraction", "landmark", "museum", "park", "beach", "viewpoint", "nature"}


@unittest.skipUnless(os.path.exists(MATRIX), "matrix snapshot not built")
class TestMatrixSnapshotArtifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MATRIX, encoding="utf-8") as f:
            cls.doc = json.load(f)

    def test_full_coverage_n_by_n(self):
        doc = self.doc
        self.assertGreaterEqual(doc["n"], N_TOP)  # append-only expansion
        self.assertEqual(doc["n"], len(doc["ids"]))
        self.assertEqual(len(set(doc["ids"])), doc["n"], "ids must be unique")
        cov = doc["coverage"]
        self.assertEqual(cov["pairs_total"], doc["n"] * doc["n"])
        self.assertEqual(cov["cells"], len(doc["cells"]))
        self.assertEqual(cov["infeasible"], 0)  # every pair routable in bbox
        self.assertEqual(cov["haversine_seed"], 0)
        self.assertEqual(doc["snapshot"], "danang-v1")

    def test_every_pair_present(self):
        ids = self.doc["ids"]
        missing = [f"{a}->{b}" for a in ids for b in ids
                   if f"{a}->{b}" not in self.doc["cells"]]
        self.assertEqual(missing, [])

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

    def test_every_verified_poi_is_routable(self):
        """The expansion exists so verified POIs are never matrix-starved."""
        if not os.path.exists(POIS):
            self.skipTest("pois.json not present")
        with open(POIS, encoding="utf-8") as f:
            pois = json.load(f)["pois"]
        ids = set(self.doc["ids"])
        verified = [p for p in pois if p.get("verified") is True
                    and isinstance(p.get("lat"), (int, float))
                    and isinstance(p.get("lon"), (int, float))]
        missing = [p["poi_id"] for p in verified if p["poi_id"] not in ids]
        self.assertEqual(missing, [], "verified POIs missing from matrix")
        cats = [p.get("cat") for p in verified if p["poi_id"] in ids]
        non_food = [c for c in cats if c in SIGHTSEEING]
        self.assertGreaterEqual(len(non_food), 5,
                                f"need non-food coverage, got {sorted(set(non_food))}")

    def test_expansion_recorded(self):
        """Append builds must be auditable: source, categories, cell count."""
        expansions = self.doc.get("expansions") or []
        if not expansions:
            self.skipTest("artifact is the original top-N build")
        last = expansions[-1]
        self.assertEqual(last["osrm_base_url"], "http://127.0.0.1:5000")
        self.assertGreater(len(last["added_pois"]), 0)
        self.assertGreater(last["cells_added"], 0)
        self.assertEqual(last["cells_missing"], 0)
        self.assertTrue(last["by_category"])

    def test_service_reads_artifact(self):
        svc = MatrixService(os.path.dirname(MATRIX))
        self.assertEqual(len(svc.ids), self.doc["n"])
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
