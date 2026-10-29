"""Integrity test for the committed OSRM matrix snapshot (T010b, lane B; Phase 3).

Guards `BE/data/snapshots/danang-v1/matrix.json` — since Phase 3 the full
motorbike build: every snapshot POI with coordinates, routed once by
`BE/tools/build_poi_matrix.py --all` over the graph `BE/tools/osrm/
build_osrm.sh` makes with `motorbike.lua`, stored as `dense-v1`. No Docker,
no network: file checks + a `MatrixService` round-trip only. Skips when the
artifact is absent so unit runs stay green in fresh checkouts.

The profile hash check ties the artifact to the committed profile: editing
motorbike.lua (e.g. SPEED_SCALE) without rebuilding the matrix fails here.

Run from repo root: python BE/tests/unit/test_matrix_snapshot.py -v
"""

import hashlib
import json
import os
import sys
import unittest
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.matrix import (  # noqa: E402
    DENSE_FORMAT, MatrixService, load_matrix_doc)

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SNAPSHOT_DIR = os.path.join(_REPO_ROOT, "BE", "data", "snapshots", "danang-v1")
MATRIX = os.path.join(SNAPSHOT_DIR, "matrix.json")
POIS = os.path.join(SNAPSHOT_DIR, "pois.json")
PROFILE = os.path.join(_REPO_ROOT, "BE", "tools", "osrm", "motorbike.lua")
SIGHTSEEING = {"attraction", "landmark", "museum", "park", "beach", "viewpoint", "nature"}


@unittest.skipUnless(os.path.exists(MATRIX), "matrix snapshot not built")
class TestMatrixSnapshotArtifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load_matrix_doc(MATRIX)
        cls.cells = cls.doc["cells"]

    def test_full_coverage_n_by_n(self):
        doc = self.doc
        self.assertEqual(doc["format"], DENSE_FORMAT)
        self.assertEqual(doc["n"], len(doc["ids"]))
        self.assertEqual(len(set(doc["ids"])), doc["n"], "ids must be unique")
        cov = doc["coverage"]
        self.assertEqual(cov["pairs_total"], doc["n"] * doc["n"])
        self.assertEqual(cov["cells"], len(self.cells))
        self.assertEqual(cov["infeasible"], 0)  # every pair routable in bbox
        self.assertEqual(cov["haversine_seed"], 0)
        self.assertEqual(doc["snapshot"], "danang-v1")

    def test_covers_every_poi_with_coordinates(self):
        """Phase 3: built once for ALL POIs, so verifying one needs no rebuild."""
        if not os.path.exists(POIS):
            self.skipTest("pois.json not present")
        with open(POIS, encoding="utf-8") as f:
            pois = json.load(f)["pois"]
        routable = [p["poi_id"] for p in pois
                    if isinstance(p.get("lat"), (int, float))
                    and isinstance(p.get("lon"), (int, float))]
        self.assertEqual(self.doc["ids"], routable)
        self.assertEqual(self.doc["top_by"], "all")
        verified = {p["poi_id"] for p in pois if p.get("verified") is True}
        cats = [p.get("cat") for p in pois if p["poi_id"] in verified]
        self.assertGreaterEqual(len([c for c in cats if c in SIGHTSEEING]), 5)

    def test_osrm_labelled_and_never_silent_zero(self):
        doc = self.doc
        self.assertEqual(doc["source"], "osrm")
        self.assertEqual(doc["confidence"], "high")
        minutes, km = self.cells._minutes, self.cells._km
        for i, row in enumerate(minutes):
            self.assertEqual((row[i], km[i][i]), (0, 0.0), doc["ids"][i])
            for j, value in enumerate(row):
                if i != j:
                    # Neighbours sharing a road node have km 0.0, never 0 min.
                    self.assertGreaterEqual(value, 1, (i, j))
                    self.assertGreaterEqual(km[i][j], 0.0, (i, j))

    def test_built_with_the_committed_motorbike_profile(self):
        osrm = self.doc["osrm"]
        self.assertEqual(self.doc["mode"], "motorbike")
        self.assertEqual(osrm["profile"], "BE/tools/osrm/motorbike.lua")
        with open(PROFILE, "rb") as f:
            self.assertEqual(osrm["profile_sha256"],
                             hashlib.sha256(f.read()).hexdigest(),
                             "motorbike.lua changed: rebuild graph + matrix")
        self.assertTrue(osrm["osrm_image"].endswith(":v5.27.1"))
        self.assertTrue(osrm["extract_md5"])
        self.assertTrue(osrm["osm_timestamp"])

    def test_service_reads_artifact(self):
        svc = MatrixService(os.path.dirname(MATRIX))
        self.assertEqual(len(svc.ids), self.doc["n"])
        a, b = self.doc["ids"][0], self.doc["ids"][1]
        self.assertEqual(svc.minutes(a, a), (0, "cache"))
        minutes, source = svc.minutes(a, b)
        self.assertGreaterEqual(minutes, 1)
        self.assertEqual(source, "osrm")
        self.assertEqual(svc.minutes_or_none(a, b)[1], "osrm")

    def test_built_against_a_local_osrm(self):
        # The build host's port differs (macOS AirPlay owns 5000); the
        # artifact must still come from a loopback osrm-routed, not a
        # public demo server.
        url = urlparse(self.doc["osrm_base_url"])
        self.assertEqual(url.hostname, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
