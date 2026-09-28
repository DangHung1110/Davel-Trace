"""Contract test POST /v1/parse (T012, lane C). Shape per contracts/api.md.

LLM gateway is monkeypatched (no network): full slots -> TripRequest
JSON; empty city -> needs_clarification.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.services import parser as parser_svc  # noqa: E402

FULL = {"city": "Đà Nẵng", "date": "", "start_time": "07:00",
        "end_time": "18:00", "days": 1, "travelers": 2, "budget": 3000000,
        "transport": ["motorbike"], "must_visit": [], "avoid": [],
        "activities": ["biển"], "food_prefs": [], "order_prefs": [],
        "hard_constraints": [], "soft_prefs": [], "uncertainties": []}

client = TestClient(main_mod.app)


class TestParseContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._real = parser_svc.llm_gateway.complete_json
        parser_svc.llm_gateway.complete_json = lambda prompt, schema: dict(FULL)

    @classmethod
    def tearDownClass(cls):
        parser_svc.llm_gateway.complete_json = cls._real

    def test_parse_full_shape(self):
        r = client.post("/v1/parse", json={"text": "đi Đà Nẵng", "user_id": "u1"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        for k in ("city", "start_time", "end_time", "days", "travelers",
                  "budget", "must_visit", "avoid", "order_prefs"):
            self.assertIn(k, body)
        self.assertEqual(body["city"], "đà-nẵng")

    def test_parse_needs_clarification(self):
        parser_svc.llm_gateway.complete_json = lambda prompt, schema: dict(FULL, city="")
        try:
            r = client.post("/v1/parse", json={"text": "đi chơi"})
        finally:
            parser_svc.llm_gateway.complete_json = TestParseContract._real
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["needs_clarification"], ["city"])


if __name__ == "__main__":
    unittest.main()
