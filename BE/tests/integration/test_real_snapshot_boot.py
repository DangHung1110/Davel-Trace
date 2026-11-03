"""N7: boot the app against the REAL working snapshot (742 POIs).

Everything else in the suite pins the LOCKED 7-POI seed (`BE/tests/conftest.py`
-> `data/snapshots/danang-v1`), so a broken real pool (missing matrix
coverage, empty retrieval) would still be green. This integration test points
`SNAPSHOT_DIR` at the big working snapshot `BE/data/snapshots/danang-v1` and
checks, at the retrieval seam only (no LLM, no solver full run):

- the app boots and `/v1/health` reports that snapshot,
- the snapshot loads through the app's own loader with the working pool size
  (742 POIs) and > 300 verified POIs,
- the matrix covers EVERY verified POI (as source and as target),
- one beach `retrieve()` call returns non-empty candidates plus the
  `needs_verification` explanation (B4 shape on real data).

It also pins the N6 CORS allow-list: explicit harness origins, never "*", and
`CORS_ORIGINS` only ADDING to them.

Run: python BE/tests/integration/test_real_snapshot_boot.py -v  (or pytest)
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.routers import evaluate as evaluate_router  # noqa: E402
from BE.app.services import retrieval as retrieval_svc  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
REAL_DIR = os.path.join(REPO_ROOT, "BE", "data", "snapshots", "danang-v1")
REAL_POI_COUNT = 742

BEACH_TRIP = {
    "trip_id": "n7-beach", "user_id": "u1", "city": "da-nang",
    "start_time": "07:00", "end_time": "18:00", "days": 1,
    "travelers": 2, "budget": 3000000, "transport": ["motorbike"],
    "must_visit": [], "avoid": [], "activities": ["biển"],
    "food_prefs": [], "order_prefs": [],
}


class TestRealSnapshotBoot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The runtime reads SNAPSHOT_DIR in get_settings() on every request, so
        # patching the env before the first request is enough to boot the app
        # against the big snapshot instead of the 7-POI seed.
        cls._env = mock.patch.dict(os.environ, {"SNAPSHOT_DIR": REAL_DIR})
        cls._env.start()
        cls.client = TestClient(main_mod.app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls):
        cls._env.stop()

    def test_health_reports_the_real_snapshot(self):
        r = self.client.get("/v1/health")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["snapshot"], "danang-v1")

    def test_real_snapshot_loads_with_the_working_pool(self):
        loaded = evaluate_router.load_eval_context(REAL_DIR)
        self.assertIsNotNone(loaded, f"real snapshot missing at {REAL_DIR}")
        pois, _cells = loaded
        self.assertEqual(len(pois), REAL_POI_COUNT)
        verified = [pid for pid, poi in pois.items() if poi.get("verified")]
        self.assertGreater(len(verified), 300)

    def test_matrix_covers_every_verified_poi(self):
        loaded = evaluate_router.load_eval_context(REAL_DIR)
        self.assertIsNotNone(loaded)
        pois, cells = loaded
        self.assertTrue(cells, "matrix.json has no cells")
        verified = {pid for pid, poi in pois.items() if poi.get("verified")}
        sources = {key.split("->", 1)[0] for key in cells}
        targets = {key.split("->", 1)[1] for key in cells}
        self.assertEqual(sorted(verified - sources), [],
                         "verified POIs missing from the matrix as source")
        self.assertEqual(sorted(verified - targets), [],
                         "verified POIs missing from the matrix as target")

    def test_beach_retrieval_returns_candidates(self):
        pois = retrieval_svc.load_pois_json(os.path.join(REAL_DIR, "pois.json"))
        self.assertEqual(len(pois), REAL_POI_COUNT)
        result = retrieval_svc.retrieve(dict(BEACH_TRIP), pois)
        self.assertTrue(result["candidates"], "beach retrieval returned no candidates")
        # The explanation (B4) is part of the same retrieval call and is
        # non-trivial on the real snapshot: 742 POIs, only some verified.
        self.assertTrue(result["needs_verification"])
        self.assertTrue(any(c["poi_id"] for c in result["candidates"]))


class TestCorsAllowList(unittest.TestCase):
    HARNESS = ("http://127.0.0.1:5500", "http://localhost:5500")

    def test_allow_list_is_the_harness_never_wildcard(self):
        origins = main_mod.cors_origins()
        self.assertNotIn("*", origins)
        for origin in self.HARNESS:
            self.assertIn(origin, origins)

    def test_harness_origin_gets_a_cors_response(self):
        client = TestClient(main_mod.app, raise_server_exceptions=False)
        r = client.options(
            "/v1/health",
            headers={"Origin": "http://127.0.0.1:5500",
                     "Access-Control-Request-Method": "GET"})
        self.assertEqual(
            r.headers.get("access-control-allow-origin"),
            "http://127.0.0.1:5500")
        r = client.options(
            "/v1/health",
            headers={"Origin": "https://evil.example",
                     "Access-Control-Request-Method": "GET"})
        self.assertNotEqual(r.headers.get("access-control-allow-origin"),
                            "https://evil.example")

    def test_env_extends_the_allow_list(self):
        with mock.patch.dict(os.environ,
                             {"CORS_ORIGINS": "http://127.0.0.1:8080, https://x.test/ "}):
            origins = main_mod.cors_origins()
        self.assertIn("http://127.0.0.1:8080", origins)
        self.assertIn("https://x.test", origins)
        for origin in self.HARNESS:  # extras never replace the harness
            self.assertIn(origin, origins)


if __name__ == "__main__":
    unittest.main()
