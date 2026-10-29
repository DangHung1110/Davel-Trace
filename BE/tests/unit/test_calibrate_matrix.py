"""Matrix calibration tool (Phase 3). Injected transport: no network, no key.

- sampling is seeded, spread over the km bands, never a self pair;
- VietMap/OSRM answers become APE stats, per band and overall, and the
  SPEED_SCALE suggestion is fitted on one half, judged on the other;
- the key is read from env/.env and never reaches the report or an error.

Run from repo root: python -m pytest BE/tests/unit/test_calibrate_matrix.py -q
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.matrix import DenseCells  # noqa: E402
from BE.tools import calibrate_matrix as cal  # noqa: E402
from BE.tools.osrm import grid_search  # noqa: E402

KEY = "test-key-123"

# 12 POIs on a line, 1.1 km apart: pairs cover every band.
IDS = [f"p{i}" for i in range(12)]
POIS = [{"poi_id": pid, "name": pid.upper(), "lat": 16.0 + 0.01 * i,
         "lon": 108.2} for i, pid in enumerate(IDS)]
KM = [[round(abs(i - j) * 1.1 * (2 if abs(i - j) > 6 else 1), 2)
       for j in range(12)] for i in range(12)]
MINUTES = [[0 if i == j else max(1, round(KM[i][j] * 2)) for j in range(12)]
           for i in range(12)]


def _index(lat):
    return round((float(lat) - 16.0) / 0.01)


def fake_transport(ratio=1.25, fail_every=0):
    """VietMap = matrix minutes * ratio; OSRM /route = matrix exactly."""
    calls = {"n": 0}

    def transport(url, _timeout):
        calls["n"] += 1
        parsed = urlsplit(url)  # urlparse would cut the path at ';'
        if "/route/v1/driving/" in parsed.path:
            a, b = parsed.path.rsplit("/", 1)[1].split(";")
            i, j = _index(a.split(",")[1]), _index(b.split(",")[1])
            return {"code": "Ok", "routes": [{"distance": KM[i][j] * 1000,
                                              "duration": MINUTES[i][j] * 60}]}
        query = parse_qs(parsed.query)
        assert query["apikey"] == [KEY] and query["vehicle"] == ["motorcycle"]
        if fail_every and calls["n"] % fail_every == 0:
            raise OSError(f"connection reset for {url}")
        (pa, pb) = query["point"]
        i, j = _index(pa.split(",")[0]), _index(pb.split(",")[0])
        return {"paths": [{"distance": KM[i][j] * 1000,
                           "time": MINUTES[i][j] * ratio * 60000}]}
    return transport


def _snapshot():
    directory = tempfile.mkdtemp(prefix="cal_")
    with open(os.path.join(directory, "pois.json"), "w", encoding="utf-8") as f:
        json.dump({"pois": POIS}, f)
    with open(os.path.join(directory, "matrix.json"), "w", encoding="utf-8") as f:
        json.dump({"format": "dense-v1", "ids": IDS, "n": 12, "mode": "motorbike",
                   "osrm": {"osm_timestamp": "t", "profile_sha256": "f" * 64},
                   "minutes": MINUTES, "km": KM}, f)
    return directory


class TestSampling(unittest.TestCase):
    def test_seeded_stratified_no_self_pairs(self):
        cells = DenseCells(IDS, MINUTES, KM)
        first = cal.sample_pairs(IDS, cells, 10, seed=7)
        again = cal.sample_pairs(IDS, cells, 10, seed=7)
        self.assertEqual(first, again)
        self.assertEqual(len(first), 10)
        self.assertEqual(sorted({p["band"] for p in first}), [0, 1, 2, 3, 4])
        for p in first:
            self.assertNotEqual(p["from"], p["to"])
            lo, hi = cal.BANDS[p["band"]]
            self.assertTrue(lo <= p["osrm_km"] < hi)


class TestRun(unittest.TestCase):
    def run_main(self, transport, *extra, env=None):
        directory = _snapshot()
        with mock.patch.dict(os.environ, env if env is not None
                             else {cal.KEY_NAME: KEY}, clear=False):
            if env == {}:
                os.environ.pop(cal.KEY_NAME, None)
            code = cal.main(["--snapshot-dir", directory, "--pairs", "10",
                             "--env-file", os.path.join(directory, "none"),
                             *extra],
                            transport=transport, wait=lambda _s: None)
        with open(os.path.join(directory, "MATRIX_CALIBRATION.json"),
                  encoding="utf-8") as f:
            doc = json.load(f)
        with open(os.path.join(directory, "MATRIX_CALIBRATION.md"),
                  encoding="utf-8") as f:
            text = f.read()
        return code, doc, text

    def test_bias_is_measured_and_scale_suggested(self):
        code, doc, text = self.run_main(fake_transport(ratio=1.5),
                                        "--osrm-url", "http://osrm")
        rep = doc["report"]
        self.assertEqual(rep["pairs_ok"], 10)
        # OSRM = VietMap / 1.5: exact seconds show the pure model bias.
        self.assertAlmostEqual(rep["time_exact"]["bias"], -1 / 3, places=3)
        self.assertAlmostEqual(rep["time_exact"]["mape"], 1 / 3, places=3)
        self.assertAlmostEqual(rep["distance"]["mape"], 0.0, places=3)
        scale = rep["speed_scale"]
        self.assertEqual(scale["fitted_with"], "osrm_exact_min")
        self.assertAlmostEqual(scale["multiply_speed_scale_by"], 0.667, places=3)
        self.assertAlmostEqual(scale["holdout_projected"]["mape"], 0.0, places=3)
        self.assertFalse(rep["passed"])  # 33 % > 20 % target
        self.assertEqual(code, 1)
        self.assertIn("SPEED_SCALE suggestion", text)

    def test_target_met_passes(self):
        code, doc, _ = self.run_main(fake_transport(ratio=1.05))
        self.assertTrue(doc["report"]["passed"])
        self.assertEqual(code, 0)

    def test_key_never_leaks_and_failures_are_kept(self):
        code, doc, text = self.run_main(fake_transport(fail_every=3))
        blob = json.dumps(doc) + text
        self.assertNotIn(KEY, blob)
        errors = [p["error"] for p in doc["pairs"] if p.get("error")]
        self.assertTrue(errors)
        self.assertTrue(all("REDACTED" in e for e in errors))
        self.assertLess(doc["report"]["pairs_ok"], 10)

    def test_missing_key_stops_before_network(self):
        directory = _snapshot()
        called = []
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(cal.KEY_NAME, None)
            code = cal.main(["--snapshot-dir", directory,
                             "--env-file", os.path.join(directory, "none")],
                            transport=lambda *a: called.append(a))
        self.assertEqual(code, 2)
        self.assertEqual(called, [])


class TestReadKey(unittest.TestCase):
    def test_env_file_parsing(self):
        path = os.path.join(tempfile.mkdtemp(prefix="env_"), ".env")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# comment\nOTHER=1\nVIETMAP_API_KEY = 'abc123'\n")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(cal.KEY_NAME, None)
            self.assertEqual(cal.read_key(path), "abc123")
            os.environ[cal.KEY_NAME] = "from-env"
            self.assertEqual(cal.read_key(path), "from-env")


class TestGridSearch(unittest.TestCase):
    """Pure parts of BE/tools/osrm/grid_search.py (the builds need docker)."""

    def test_variant_replaces_both_knobs_once(self):
        with open(grid_search.PROFILE, encoding="utf-8") as f:
            profile = f.read()
        out = grid_search.variant(profile, 0.9, 0.3)
        self.assertIn("\nSPEED_SCALE = 0.9\n", out)
        self.assertIn("\nCLASS_SPREAD = 0.3\n", out)
        with self.assertRaises(ValueError):
            grid_search.variant("SPEED_SCALE = 1\n", 1.0, 1.0)

    def test_committed_profile_holds_the_fitted_knobs(self):
        with open(grid_search.PROFILE, encoding="utf-8") as f:
            profile = f.read()
        self.assertIn("\nSPEED_SCALE = 1.15\n", profile)
        self.assertIn("\nCLASS_SPREAD = 0.1\n", profile)

    def test_score_splits_like_calibrate_report(self):
        rows = [(10.0, 10.0, 1.0, 1.0, 0), (12.0, 10.0, 1.0, 1.0, 0),
                (10.0, 10.0, 2.0, 1.0, 1), (8.0, 10.0, 1.0, 1.0, 1)]
        out = grid_search.score(rows)
        self.assertEqual(out["fit"], 0.0)        # rows 0 and 2
        self.assertEqual(out["holdout"], 0.2)    # rows 1 and 3
        self.assertEqual(out["km_mape"], 0.25)
        self.assertEqual(out["bias_by_band"], {"0": 0.1, "1": -0.1})


if __name__ == "__main__":
    unittest.main()
