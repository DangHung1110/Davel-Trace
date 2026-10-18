"""Contract test POST /v1/itinerary/select (T033e, lane C — closes US4).

Select 1 of 3 stub plans -> active_id correct, others kept for compare;
unknown id -> 404 envelope.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.routers import select as select_mod  # noqa: E402

PLANS = [{"itinerary_id": f"it-{p}", "profile": p,
          "total_cost": c, "preference": s}
         for p, c, s in (("savings", 0, 4.2), ("balanced", 200000, 4.5),
                         ("experience", 500000, 4.8))]

client = TestClient(main_mod.app, raise_server_exceptions=False)


class TestSelectContract(unittest.TestCase):
    def setUp(self):
        select_mod.reset_store()
        select_mod.register(PLANS)

    def test_select_middle_plan(self):
        r = client.post("/v1/itinerary/select", json={"itinerary_id": "it-balanced"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"active_id": "it-balanced"})
        store = select_mod.get_store()
        self.assertEqual(store["active_id"], "it-balanced")
        self.assertEqual(store["selected"], "it-balanced")
        self.assertEqual(sorted(store["plans"]),
                         ["it-balanced", "it-experience", "it-savings"])
        print(f"\n active: {store['active_id']} kept: {sorted(store['plans'])}")

    def test_failed_gate_does_not_select_plan(self):
        with patch("BE.app.routers.select.gate_stub.all_pass",
                   return_value={"passed": False, "failed": ["BCS"]}):
            r = client.post("/v1/itinerary/select",
                            json={"itinerary_id": "it-balanced"})

        self.assertEqual(r.status_code, 422)
        self.assertEqual(set(r.json()), {"error", "message"})
        self.assertEqual(r.json()["error"], "GATE_FAILED")
        self.assertIn("BCS", r.json()["message"])
        self.assertIsNone(select_mod.get_store()["active_id"])
        self.assertIsNone(select_mod.get_store()["selected"])

    def test_unknown_id_404_envelope(self):
        r = client.post("/v1/itinerary/select", json={"itinerary_id": "it-ghost"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "UNKNOWN_ITINERARY")


if __name__ == "__main__":
    unittest.main()
