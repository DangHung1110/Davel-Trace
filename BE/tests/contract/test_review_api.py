"""Contract test for POST /v1/review (NOTE(test-local) LLM layer-3 review).

Pins: both input shapes (plan / itinerary_id), issue normalisation, and the
"never 500 the harness" fallback when the LLM is unavailable.

Run: PYTHONPATH=BE python -m unittest BE.tests.contract.test_review_api
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.routers import review as review_mod  # noqa: E402
from BE.app.routers import select as select_mod  # noqa: E402
from BE.app.services.llm import LLMError  # noqa: E402

client = TestClient(main_mod.app, raise_server_exceptions=False)

PLAN = {
    "itinerary_id": "rev-1",
    "activities": [
        {"poi_id": "r1", "start": "11:15", "end": "12:15"},
        {"poi_id": "r2", "start": "12:25", "end": "13:25"},
    ],
    "_context": {"trip": {"food_prefs": ["hải sản"]}, "pois": [], "travel": {}},
}


class TestReviewApi(unittest.TestCase):
    def test_review_returns_normalised_issues(self):
        llm_out = {"issues": [
            {"issue": "an trua 2 lan", "severity": "HIGH", "suggestion": "bo 1 bua"},
            {"issue": "", "severity": "low"},        # dropped: empty issue
            {"nope": True},                          # dropped: no issue text
        ]}
        with mock.patch.object(review_mod.llm_gateway, "complete_json",
                               return_value=llm_out) as m:
            r = client.post("/v1/review", json={"plan": PLAN})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body, {"issues": [{
            "issue": "an trua 2 lan", "severity": "high",
            "suggestion": "bo 1 bua"}]})
        prompt = m.call_args[0][0]
        self.assertTrue(prompt.rstrip().endswith("/no_think"))
        self.assertIn("hải sản", prompt)

    def test_review_llm_failure_is_soft(self):
        with mock.patch.object(review_mod.llm_gateway, "complete_json",
                               side_effect=LLMError("transport", "down")):
            r = client.post("/v1/review", json={"plan": PLAN})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"issues": [], "note": "LLM_UNAVAILABLE"})

    def test_review_reads_the_select_store_by_id(self):
        select_mod.reset_store()
        stored = {**PLAN, "activities": [
            {"poi_id": "r1", "start": "18:00", "end": "19:00"}]}
        select_mod.register([stored])
        with mock.patch.object(review_mod.llm_gateway, "complete_json",
                               return_value={"issues": []}):
            r = client.post("/v1/review", json={"itinerary_id": "rev-1"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"issues": []})
        select_mod.reset_store()

    def test_review_drops_issue_refuted_by_a2(self):
        """TASK-3: a 'double lunch' claim dies when A1+A2 provably pass."""
        pois = {
            "r1": {"poi_id": "r1", "cat": "restaurant", "name": "Quan 1",
                   "verified": True, "opening_hours": ["00:00-23:59"]},
            "r2": {"poi_id": "r2", "cat": "restaurant", "name": "Quan 2",
                   "verified": True, "opening_hours": ["00:00-23:59"]},
            "beach": {"poi_id": "beach", "cat": "beach", "name": "Bien",
                      "verified": True, "opening_hours": ["00:00-23:59"]},
        }
        plan = {"activities": [
            {"poi_id": "r1", "start": "07:00", "end": "08:00"},
            {"poi_id": "beach", "start": "09:00", "end": "10:00"},
            {"poi_id": "r2", "start": "12:51", "end": "13:51"},
        ]}
        llm_out = {"issues": [
            {"issue": "Ăn trưa 2 lần trong cùng một ngày",
             "severity": "high", "suggestion": "bo 1 bua"},
            {"issue": "Bar/hộp đêm buổi sáng", "severity": "high",
             "suggestion": "doi gio"},
        ]}
        with mock.patch.object(review_mod, "_poi_index", return_value=pois), \
                mock.patch.object(review_mod.llm_gateway, "complete_json",
                                  return_value=llm_out):
            r = client.post("/v1/review", json={"plan": plan})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"issues": []})

    def test_review_keeps_a_real_close_restaurant_pair(self):
        """A2 fails (10:49 vs 11:05): the lunch issue is NOT suppressed."""
        pois = {
            "r1": {"poi_id": "r1", "cat": "restaurant", "name": "Quan 1",
                   "verified": True, "opening_hours": ["00:00-23:59"]},
            "r2": {"poi_id": "r2", "cat": "restaurant", "name": "Quan 2",
                   "verified": True, "opening_hours": ["00:00-23:59"]},
        }
        plan = {"activities": [
            {"poi_id": "r1", "start": "10:49", "end": "11:49"},
            {"poi_id": "r2", "start": "12:05", "end": "13:05"},
        ]}
        llm_out = {"issues": [{"issue": "Ăn trưa 2 lần", "severity": "high",
                               "suggestion": "bo 1 bua"}]}
        with mock.patch.object(review_mod, "_poi_index", return_value=pois), \
                mock.patch.object(review_mod.llm_gateway, "complete_json",
                                  return_value=llm_out):
            r = client.post("/v1/review", json={"plan": plan})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(r.json()["issues"]), 1)

    def test_unknown_itinerary_id_is_404(self):
        select_mod.reset_store()
        r = client.post("/v1/review", json={"itinerary_id": "nope"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "UNKNOWN_ITINERARY")

    def test_missing_input_is_422(self):
        r = client.post("/v1/review", json={})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
