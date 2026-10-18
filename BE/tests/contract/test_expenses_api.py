"""Contract test for expense endpoints (T035, lane C)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.services import expenses as ex  # noqa: E402

client = TestClient(main_mod.app, raise_server_exceptions=False)


class TestExpensesApi(unittest.TestCase):
    def setUp(self):
        ex.reset()
        ex.set_budget("t1", 3000000)

    def test_post_and_summary(self):
        for label, amount, kind in (("Mi Quang", 120000, "food"),
                                    ("Ve", 60000, "ticket"),
                                    ("Xe", 200000, "transport")):
            r = client.post("/v1/expenses",
                            json={"trip_id": "t1", "label": label,
                                  "amount": amount, "kind": kind})
            self.assertEqual(r.status_code, 201, r.text)
        r = client.get("/v1/expenses/summary", params={"trip_id": "t1"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual((body["budget"], body["spent"], body["left"]),
                         (3000000, 380000, 2620000))
        self.assertEqual(body["alert"], "")
        print(f"\n summary: {body}")

    def test_bad_kind_400_envelope(self):
        r = client.post("/v1/expenses",
                        json={"trip_id": "t1", "label": "x",
                              "amount": 100, "kind": "shopping"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "BAD_EXPENSE")


if __name__ == "__main__":
    unittest.main()
