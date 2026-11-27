"""POST /v1/itinerary on danang-v2 pays for what the stops need (specs/025).

A family of four that must see Cầu Vàng and Fantasy Park from the Sala hotel buys
four Sun World tickets (the cable car is in that ticket): before, the plan said
200,000 VND, only lunch. A budget that cannot pay the tickets gets no plan and is
told so. The plan's total_cost, its `access_fees` and an independent sum over the
raw data (`audit_plans.audit_fee`) agree.

One profile per request; weather mocked offline. About 10 s.
Run: python -m pytest BE/tests/integration/test_access_fees_v2.py -q
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
from BE.app.services import trip_ctx  # noqa: E402
from BE.common import load_pois  # noqa: E402
from BE.tools.audit_plans import audit_fee, transfer_fares  # noqa: E402

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "snapshots", "danang-v2")
SALA = "ChIJMeyhoXgXQjERqCs6CuNR5yI"          # Sala Danang Beach Hotel
SUN_WORLD = "ChIJyUQ4aw72QTERCXl5YV-4U1w"
FAMILY = {"party_type": "family", "pace": 1, "fitness": 1}

client = TestClient(main_mod.app)


@unittest.skipUnless(os.path.exists(os.path.join(SNAPSHOT, "transfers.json")),
                     "danang-v2 has no transfers.json")
class TestAccessFeesOnDanangV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pois = load_pois(SNAPSHOT, by_id=True)
        cls.fares = transfer_fares(SNAPSHOT)
        cls._settings = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir=SNAPSHOT,
                                                      snapshot_name="danang-v2")

    @classmethod
    def tearDownClass(cls):
        itinerary_mod.get_settings = cls._settings

    def plan(self, budget):
        body = {"trip": {"start_time": "08:00", "end_time": "20:00", "budget": budget,
                         "travelers": 4, "profile": FAMILY, "origin": {"poi_id": SALA},
                         "must_visit": ["Cầu Vàng", "Fantasy Park"]},
                "profiles": ["balanced"]}
        with mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                               side_effect=RuntimeError("offline test")):
            r = client.post("/v1/itinerary", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["plans"][0]

    def test_the_family_buys_four_sun_world_tickets(self):
        plan = self.plan(6_000_000)
        self.assertTrue(plan["passed"], plan.get("violations"))
        ids = [a["poi_id"] for a in plan["activities"]]
        bridge, park = (next(pid for pid, p in self.pois.items() if p["name"] == name)
                        for name in ("Cầu Vàng", "Fantasy Park"))
        self.assertTrue({bridge, park} <= set(ids))
        self.assertNotIn(SUN_WORLD, ids)
        ticket = next(f for f in plan["access_fees"] if f["key"] == SUN_WORLD)
        self.assertEqual((ticket["vnd_per_person"], ticket["travelers"], ticket["vnd"]),
                         (850000, 4, 3400000))
        self.assertTrue({bridge, park} <= set(ticket["for"]))
        self.assertGreaterEqual(plan["total_cost"], 3400000)
        self.assertEqual(plan["total_cost"], 4 * audit_fee(plan["activities"], self.pois, self.fares))

    def test_a_budget_short_of_the_tickets_gets_no_plan_and_says_why(self):
        plan = self.plan(3_000_000)
        self.assertEqual(plan["activities"], [])
        self.assertTrue(any("ngan sach" in w for w in plan.get("warnings") or []), plan.get("warnings"))


if __name__ == "__main__":
    unittest.main()
