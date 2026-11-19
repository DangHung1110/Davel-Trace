"""review_v21 export -> decisions + human_verify source files (BE/tools/ingest_review.py)."""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

from BE.tools.ingest_review import convert  # noqa: E402
from migrate_v2 import apply_decision  # noqa: E402

from BE.tests.unit.test_poi_view_v21 import rec  # noqa: E402

EXPORT = {
    "schema": "review_v21", "exported_at": "2026-11-20",
    "questions": {"Q3": {"choice": "cach_ly", "default": True, "note": None}},
    "names": [{"poi_id": "n1", "name": "Clover Spa", "name_was": "Clover Spa - Best Spa"},
              {"poi_id": "n2", "name": "Same", "name_was": "Same"}],
    "status": [{"poi_id": "r1", "status": "active", "reason": "ok"}],
    "duplicates": [{"a": "d1", "b": "d2", "decision": "keep_a"},
                   {"a": "d3", "b": "d4", "decision": "distinct"}],
    "verify": [{"poi_id": "v1", "hours": "07:00-17:00", "price_tier": "cheap",
                "evidence_url": "https://example.org"},
               {"poi_id": "v2", "price_tier": "free"}],
    "old_town": {"parent": "osm:parent", "include": ["o1"], "exclude": ["o2"]},
}


class TestIngestReview(unittest.TestCase):
    def test_convert(self):
        dec, ver = convert(EXPORT)
        it = dec["items"]
        self.assertEqual(it["n1"], {"name": "Clover Spa"})
        self.assertNotIn("n2", it)                       # unchanged name is not a decision
        self.assertEqual(it["r1"]["status"], "active")
        self.assertEqual(it["d2"]["status"], "excluded")
        self.assertNotIn("d3", it)
        self.assertEqual(it["o1"], {"requires_ticket_of": "osm:parent"})
        self.assertIsNone(it["o2"]["requires_ticket_of"])
        by = {v["poi_id"]: v for v in ver["items"]}
        self.assertEqual(by["v1"]["verified_by"], "human")
        self.assertEqual(by["v2"]["verified_by"], "user")
        self.assertEqual(by["v2"]["checked_at"], "2026-11-20")

    def test_old_town_decision_sets_included_and_back(self):
        r = rec(tier="cheap")
        apply_decision(r, {"requires_ticket_of": "osm:parent", "_file": "d.json"})
        self.assertEqual((r["requires_ticket_of"], r["price"]["tier"]), ("osm:parent", "included"))
        apply_decision(r, {"requires_ticket_of": None, "_file": "d.json"})
        self.assertEqual((r["requires_ticket_of"], r["price"]["tier"]), (None, None))

    def test_rejects_other_files(self):
        with self.assertRaises(ValueError):
            convert({"schema": "x"})


if __name__ == "__main__":
    unittest.main()
