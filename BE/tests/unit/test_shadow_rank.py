import tempfile
import unittest
from pathlib import Path

from BE.app.services.acceptance_store import AcceptanceStore
from BE.app.services.planning_readiness import build_readiness
from BE.app.services.shadow_rank import anonymize_candidates, consensus, stable_canary


class TestShadowRank(unittest.TestCase):
    def test_anonymization_uses_neutral_ids_and_no_profile_brand(self):
        candidates = [
            {
                "itinerary_id": "real-a",
                "profile": "premium-brand",
                "activities": [{"poi_id": "beach", "start": "08:00", "end": "09:00"}],
                "total_cost": 10,
            }
        ]
        public, mapping = anonymize_candidates(candidates)
        self.assertEqual(mapping, {"A": "real-a"})
        self.assertEqual(public[0]["candidate_id"], "A")
        self.assertNotIn("premium-brand", str(public))

    def test_consensus_requires_forward_reverse_agreement(self):
        mapping = {"A": "it-1", "B": "it-2"}
        reverse_mapping = {"A": "it-2", "B": "it-1"}
        agreed = consensus({"winner": "A"}, {"winner": "B"}, mapping, reverse_mapping)
        disagreed = consensus({"winner": "A"}, {"winner": "A"}, mapping, reverse_mapping)
        self.assertEqual(agreed["winner_id"], "it-1")
        self.assertTrue(agreed["swap_consistent"])
        self.assertIsNone(disagreed["winner_id"])
        self.assertFalse(disagreed["swap_consistent"])

    def test_canary_is_stable_and_capped(self):
        self.assertEqual(stable_canary("trip-7", 0.1), stable_canary("trip-7", 0.1))
        self.assertFalse(stable_canary("trip-7", 9.0))

    def test_zero_evidence_readiness_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AcceptanceStore(str(Path(tmp) / "accepted.db"))
            readiness = build_readiness(store)
        self.assertFalse(readiness["pairwise_learning"]["enabled"])
        self.assertFalse(readiness["full_day_learning"]["enabled"])
        self.assertFalse(readiness["accepted_day_retrieval"]["enabled"])
        self.assertFalse(readiness["judge"]["promotion_ready"])


if __name__ == "__main__":
    unittest.main()
