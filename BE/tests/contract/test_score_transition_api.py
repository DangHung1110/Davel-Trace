"""Contract test for POST /v1/score-transition (S7, contracts/api.md).

The scorer service is patched so the test pins the wire shape and the exact
service arguments without loading the model or touching the network.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402

client = TestClient(main_mod.app, raise_server_exceptions=False)

A = {"poi_id": "p1", "type": "attraction", "intensity": 3, "rating": 4.5}
B = {"poi_id": "p2", "type": "restaurant", "intensity": 1, "rating": 4.2}
USER = {"pace": 2, "fitness": 2, "spending_level": 2, "outdoor_bias": 0.5}


class TestScoreTransitionApi(unittest.TestCase):
    @mock.patch("BE.app.routers.scorer.scorer_svc.score_transition")
    def test_score_transition_contract(self, score_mock):
        score_mock.return_value = 0.82

        r = client.post("/v1/score-transition",
                        json={"a": A, "b": B, "user": USER})

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(set(body), {"score"})
        self.assertIsInstance(body["score"], float)
        self.assertEqual(body["score"], 0.82)
        score_mock.assert_called_once_with(A, B, USER)


if __name__ == "__main__":
    unittest.main()
