"""Every v1 plan carries J's terms of the day it shows (`_features`), on danang-v2.

`_features.raw` is read at the solver's own times and must add up to the objective
CP-SAT reported; `_features.shown` is read at the times the plan shows. The public
response drops the key (leading underscore); the plan store keeps it for offline
learning. Weather is mocked offline like the other real-snapshot tests.

Run: python -m pytest BE/tests/integration/test_plan_features.py -q
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.routers import select as select_svc  # noqa: E402
from BE.app.services import objective, trip_ctx  # noqa: E402

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "snapshots", "danang-v2")
COUPLE = {"party_type": "couple", "pace": 2, "fitness": 2}
DAY = {"start_time": "08:00", "end_time": "20:00", "budget": 3_000_000, "days": 1,
       "travelers": 2, "profile": COUPLE}

client = TestClient(main_mod.app)


@unittest.skipUnless(os.path.exists(os.path.join(SNAPSHOT, "matrix.json")),
                     "snapshot BE/data/snapshots/danang-v2 missing")
@unittest.skipIf(objective.mode() == objective.LEGACY, "features describe objective v1")
class TestPlanFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._settings = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir=SNAPSHOT,
                                                      snapshot_name="danang-v2")
        cls._weather = mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                                         side_effect=RuntimeError("offline"))
        cls._weather.start()

    @classmethod
    def tearDownClass(cls):
        cls._weather.stop()
        itinerary_mod.get_settings = cls._settings

    def _plans(self, trip: dict) -> tuple[list[dict], list[dict]]:
        resp = client.post("/v1/itinerary", json={"trip": trip})
        self.assertEqual(resp.status_code, 200)
        public = resp.json()["plans"]
        store = select_svc.get_store()["plans"]
        return public, [store[p["itinerary_id"]] for p in public]

    def test_raw_features_add_up_to_the_solver_objective(self):
        public, plans = self._plans(DAY)
        self.assertEqual(len(plans), 3)
        for pub, plan in zip(public, plans):
            feats = plan["_features"]
            self.assertNotIn("_features", pub)
            self.assertEqual(set(feats["shown"]["features"]), set(objective.FEATURES))
            self.assertAlmostEqual(feats["raw"]["j"], feats["solver_j"], delta=0.01,
                                   msg=pub.get("profile"))

    def test_the_shown_day_never_scores_below_the_solver_day(self):
        # Step 2b: a re-timing that lowers J is dropped; the stops and their order stay.
        public, plans = self._plans(DAY)
        for pub, plan in zip(public, plans):
            feats = plan["_features"]
            self.assertTrue(feats["same_stops"], pub.get("profile"))
            self.assertGreaterEqual(feats["shown"]["j"], feats["raw"]["j"] - 1e-3,
                                    pub.get("profile"))
            if not feats["retimed"]:
                self.assertEqual(feats["shown"], feats["raw"], pub.get("profile"))

    def test_a_two_day_trip_keeps_one_entry_per_day(self):
        _public, plans = self._plans({**DAY, "days": 2, "budget": 5_000_000})
        for plan in plans:
            self.assertNotIn("_features", plan)
            days = plan["_features_by_day"]
            self.assertEqual(len(days), 2)
            for feats in days:
                self.assertAlmostEqual(feats["raw"]["j"], feats["solver_j"], delta=0.01)
                self.assertGreaterEqual(feats["shown"]["j"], feats["raw"]["j"] - 1e-3)


if __name__ == "__main__":
    unittest.main()
