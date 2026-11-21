"""T061d: the shared conftest seed fixture is the LOCKED 7-POI seed.

Guards against accidentally pointing fixtures at the big working snapshot
(BE/data/snapshots/danang-v1, 764 POIs) — see CHECK-merge-blockers §2.

Run from repo root: python BE/tests/unit/test_seed_fixture.py -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.tests import conftest  # noqa: E402


class TestSeedFixture(unittest.TestCase):
    def test_seed_is_the_locked_seven_pois(self):
        pois, cells = conftest.load_seed()
        self.assertEqual(len(pois), conftest.SEED_POI_COUNT)
        self.assertTrue(all(p.get("verified") for p in pois))
        ids = [p["poi_id"] for p in pois]
        self.assertEqual(len(cells), len(ids) * len(ids))
        for a in ids:
            for b in ids:
                self.assertIn(f"{a}->{b}", cells)
        self.assertEqual(conftest.SEED_TRIP["days"], 1)

    def test_write_snapshot_roundtrips_ids(self):
        pois, cells = conftest.load_seed()
        tmp = conftest.write_snapshot(
            tempfile.mkdtemp(prefix="seedfix_"), pois, cells)
        reloaded, reloaded_cells = None, None
        import json
        with open(os.path.join(tmp, "pois.json"), encoding="utf-8") as f:
            reloaded = json.load(f)["pois"]
        with open(os.path.join(tmp, "matrix.json"), encoding="utf-8") as f:
            reloaded_cells = json.load(f)["cells"]
        self.assertEqual([p["poi_id"] for p in reloaded], [p["poi_id"] for p in pois])
        self.assertEqual(reloaded_cells, cells)


if __name__ == "__main__":
    unittest.main()
