"""US5 integration (T038, lane C). quickstart S6 via TestClient.

Budget 3,000,000 -> log 2,500,000 -> summary 500,000 left + 80% alert.

Run: python BE/tests/integration/test_us5_expense.py -v (or pytest)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.services import expenses as ex  # noqa: E402

client = TestClient(main_mod.app, raise_server_exceptions=False)


class TestUS5Expense(unittest.TestCase):
    def setUp(self):
        ex.reset()
        ex.set_budget("t1", 3000000)

    def test_s6_summary_alert(self):
        for label, amount, kind in (("An sang", 1500000, "food"),
                                    ("Ve", 400000, "ticket"),
                                    ("Xe", 600000, "transport")):
            r = client.post("/v1/expenses",
                            json={"trip_id": "t1", "label": label,
                                  "amount": amount, "kind": kind})
            self.assertEqual(r.status_code, 201, r.text)
        r = client.get("/v1/expenses/summary", params={"trip_id": "t1"})
        body = r.json()
        self.assertEqual((body["budget"], body["spent"], body["left"]),
                         (3000000, 2500000, 500000))
        self.assertEqual(body["alert"], "80%")  # 83% -> band 80%
        print(f"\n S6: left {body['left']} alert {body['alert']}")


if __name__ == "__main__":
    unittest.main()
