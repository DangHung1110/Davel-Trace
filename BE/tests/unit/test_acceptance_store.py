import tempfile
import unittest
from pathlib import Path

from BE.app.services.acceptance_store import AcceptanceStore


class TestAcceptanceStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "accepted.db")
        self.store = AcceptanceStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def _save(self, key="mobile-choice-001"):
        return self.store.save_acceptance(
            idempotency_key=key,
            itinerary_id="it-1",
            trip_id="trip-1",
            data_version="danang-test",
            request={"trip_id": "trip-1", "budget": 2_000_000},
            plan={"itinerary_id": "it-1", "activities": [{"poi_id": "beach"}]},
            gate={"passed": True, "failed_families": []},
            deterministic_rank=1,
            deterministic_score=0.9,
        )

    def test_code_first_schema_and_idempotent_insert(self):
        first = self._save()
        second = self._save()

        self.assertEqual(first["acceptance_id"], second["acceptance_id"])
        self.assertEqual(self.store.count_acceptances(), 1)
        self.assertEqual(self.store.get_acceptance(first["acceptance_id"])["plan"]["itinerary_id"], "it-1")

    def test_rows_are_returned_newest_first_without_mutation(self):
        first = self._save("mobile-choice-001")
        second = self._save("mobile-choice-002")
        items = self.store.list_acceptances("trip-1", limit=10)

        self.assertEqual([second["acceptance_id"], first["acceptance_id"]], [item["acceptance_id"] for item in items])
        self.assertEqual(first, self.store.get_acceptance(first["acceptance_id"]))


if __name__ == "__main__":
    unittest.main()
