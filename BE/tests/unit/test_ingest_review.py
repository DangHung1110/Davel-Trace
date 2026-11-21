"""review_v21 export -> decisions + human_verify source files (BE/tools/ingest_review.py)."""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

from BE.tools.ingest_review import convert, norm_hours  # noqa: E402
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

    def test_norm_hours_free_text(self):
        self.assertEqual(norm_hours("7h30 – 21h00"), (["07:30-21:00"], []))
        self.assertEqual(norm_hours("24h, luôn mở"), (["00:00-23:59"], []))
        self.assertEqual(norm_hours("Mở 24/7"), (["00:00-23:59"], []))
        self.assertEqual(norm_hours("17:00-23:00/1:00"), (["17:00-23:00"], []))
        self.assertEqual(norm_hours("8:00-11:30 và 13:30-16:30 từ thứ Hai đến thứ Bảy"),
                         (["08:00-11:30", "13:30-16:30"], ["Su"]))
        self.assertEqual(norm_hours("không rõ"), ([], []))

    def test_delete_note_becomes_excluded(self):
        dec, ver = convert({**EXPORT, "verify": [{"poi_id": "x1", "note": "Xóa địa điểm này"}]})
        self.assertEqual(dec["items"]["x1"]["status"], "excluded")
        self.assertEqual(ver["items"], [])

    def test_rejects_other_files(self):
        with self.assertRaises(ValueError):
            convert({"schema": "x"})


if __name__ == "__main__":
    unittest.main()


def test_final_policies_map_to_decisions():
    export = {"schema": "review_v21", "final": True, "exported_at": "2026-11-20",
              "policies": {"cooking": {"choice": 1, "ids": ["a", "b"]},
                           "voc": {"choice": 0, "ids": ["v"]},
                           "helio": {"choice": 0, "ids": ["h"]}},
              "auto_review": [{"poi_id": "x", "name": "X", "agree": False, "fix": "08:00-17:00"}],
              "verify": [{"poi_id": "m", "hours": "07:00-17:30", "evidence_url": "https://e.x", "closed_days": ["Tu"]}]}
    decisions, verify = convert(export)
    assert decisions["items"]["a"]["status"] == "excluded"
    assert "v" not in decisions["items"]
    assert decisions["items"]["h"]["status"] == "excluded"
    assert decisions["auto_disagree"][0]["poi_id"] == "x"
    assert verify["items"][0]["verified_by"] == "human" and verify["items"][0]["closed_days"] == ["Tu"]
