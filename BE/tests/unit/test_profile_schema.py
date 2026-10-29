"""Unit tests for the onboarding profile schema (catalog freeze).

Covers: neutral defaults, all contract keys, range validation (levels 1..3,
outdoor_bias -1..1) and the API-level 422 envelope.

Run: python -m pytest BE/tests/unit/test_profile_schema.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from pydantic import ValidationError  # noqa: E402

from BE.app.schemas.trip import TripProfile, TripRequest  # noqa: E402
from BE.app.services.profile_filter import hard_filter  # noqa: E402

FULL = {
    "party_type": "family", "trip_purpose": "leisure",
    "spending_level": 3, "pace": 1, "fitness": 2,
    "food_prefs": ["hải sản"], "allergy": ["seafood"],
    "activities": ["biển"], "outdoor_bias": -0.4,
    "accessibility": ["stroller"], "must_avoid": ["nightlife"],
    "transport": ["car"],
}


class TestProfileSchema(unittest.TestCase):
    def test_neutral_defaults(self):
        trip = TripRequest()
        profile = trip.profile
        self.assertEqual(profile["spending_level"], 2)
        self.assertEqual(profile["pace"], 2)
        self.assertEqual(profile["fitness"], 2)
        self.assertEqual(profile["outdoor_bias"], 0.0)
        for key in ("food_prefs", "allergy", "activities", "accessibility",
                    "must_avoid", "transport"):
            self.assertEqual(profile[key], [], key)

    def test_contract_keys_present(self):
        TripRequest(profile=FULL)
        keys = set(TripProfile().model_dump())
        self.assertEqual(keys, {"party_type", "trip_purpose", "spending_level",
                                "pace", "fitness", "food_prefs", "allergy",
                                "activities", "outdoor_bias", "accessibility",
                                "must_avoid", "transport"})
        self.assertEqual(TripRequest(profile=FULL).profile["allergy"],
                         ["seafood"])

    def test_partial_profile_gets_neutral_defaults(self):
        profile = TripRequest(profile={"party_type": "couple"}).profile
        self.assertEqual(profile["party_type"], "couple")
        self.assertEqual(profile["spending_level"], 2)
        self.assertEqual(profile["outdoor_bias"], 0.0)

    def test_levels_out_of_range_rejected(self):
        for key, value in (("spending_level", 0), ("spending_level", 4),
                           ("pace", 0), ("pace", 4), ("fitness", 0),
                           ("fitness", 5)):
            with self.assertRaises(ValidationError, msg=f"{key}={value}"):
                TripRequest(profile={key: value})

    def test_outdoor_bias_range(self):
        self.assertEqual(TripRequest(profile={"outdoor_bias": -1}).profile
                         ["outdoor_bias"], -1.0)
        self.assertEqual(TripRequest(profile={"outdoor_bias": 1}).profile
                         ["outdoor_bias"], 1.0)
        for value in (-1.1, 1.1, 2):
            with self.assertRaises(ValidationError):
                TripRequest(profile={"outdoor_bias": value})

    def test_api_422_envelope(self):
        """FastAPI wraps the schema error in the shared error envelope."""
        from fastapi.testclient import TestClient

        from BE.app.main import app

        client = TestClient(app)
        r = client.post("/v1/itinerary", json={
            "trip": {"profile": {"pace": 9}},
            "profiles": ["balanced"],
        })
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(set(r.json()), {"error", "message"})
        self.assertEqual(r.json()["error"], "VALIDATION_ERROR")
        self.assertIn("profile.pace", r.json()["message"])


class TestFilterCrashSafety(unittest.TestCase):
    def test_missing_tags_never_crash(self):
        pois = [{"poi_id": "bare", "name": "Bare"}, {"poi_id": "none"}]
        kept, drops = hard_filter(pois, {"allergy": ["seafood"],
                                         "must_avoid": ["trek"]})
        self.assertEqual([p["poi_id"] for p in kept], ["bare", "none"])
        self.assertEqual(drops, [])
        # Mobility treats a missing intensity as neutral (2), so a wheelchair
        # rule excludes it rather than guessing the POI is step-free.
        kept2, drops2 = hard_filter(pois, {"accessibility": ["wheelchair"]})
        self.assertEqual(kept2, [])
        self.assertEqual({d["rule"] for d in drops2}, {"accessibility"})


if __name__ == "__main__":
    unittest.main()
