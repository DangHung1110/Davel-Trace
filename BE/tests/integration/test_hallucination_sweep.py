"""Hallucination sweep (T043, lane C — closes US7). Cross-check vs snapshot.

Every POI id/name + every claimed opening-hour in itineraries and
explanations must match the snapshot: no invented POIs, no invented
hours. Explanations additionally pass explainer.validate_plan
(reason coverage). Fixture snapshot (lane C has no seed).

Run: python BE/tests/integration/test_hallucination_sweep.py -v (or pytest)
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.explainer import validate_plan  # noqa: E402

SNAPSHOT = {
    "musu": {"poi_id": "musu", "name": "Bao tang Cham",
             "opening_hours": ["07:30-17:00"]},
    "beach": {"poi_id": "beach", "name": "Bai bien My Khe",
              "opening_hours": ["00:00-23:59"]},
}

CLEAN_ITIN = {"activities": [
    {"poi_id": "musu", "name": "Bao tang Cham", "start": "08:00", "end": "09:30"},
    {"poi_id": "beach", "name": "Bai bien My Khe", "start": "10:00", "end": "12:00"}]}
CLEAN_EXP = [
    {"claim": "musu mo cua 07:30-17:00", "facts": ["snapshot hours 07:30-17:00"],
     "inference": "", "inference_marked": False, "uncertainty": [],
     "source": "snapshot", "verified": True},
]

HOURS_RE = re.compile(r"(\d{2}:\d{2})-(\d{2}:\d{2})")


def sweep(itinerary: dict, explanations: list[dict],
          snapshot: dict) -> list[str]:
    """Return violation strings (empty = clean)."""
    bad = []
    for a in itinerary.get("activities", []):
        pid = a.get("poi_id")
        if pid not in snapshot:
            bad.append(f"POI tu che: {pid}")
            continue
        if a.get("name") and a["name"] != snapshot[pid]["name"]:
            bad.append(f"ten sai: {a['name']} != {snapshot[pid]['name']}")
    texts = [a.get("name", "") for a in itinerary.get("activities", [])]
    texts += [e.get("claim", "") for e in explanations]
    texts += [f for e in explanations for f in e.get("facts", [])]
    for t in texts:
        for m in HOURS_RE.finditer(t):
            claimed = f"{m.group(1)}-{m.group(2)}"
            if not any(claimed == h for p in snapshot.values()
                       for h in p["opening_hours"]):
                bad.append(f"gio tu che: {claimed}")
    bad += validate_plan(explanations)
    return bad


class TestHallucinationSweep(unittest.TestCase):
    def test_clean_passes(self):
        self.assertEqual(sweep(CLEAN_ITIN, CLEAN_EXP, SNAPSHOT), [])

    def test_ghost_poi_caught(self):
        itin = {"activities": [{"poi_id": "atlantis", "name": "Atlantis",
                                "start": "08:00", "end": "09:00"}]}
        bad = sweep(itin, [], SNAPSHOT)
        self.assertTrue(any("POI tu che: atlantis" in b for b in bad))

    def test_wrong_name_caught(self):
        itin = {"activities": [{"poi_id": "musu", "name": "Bao tang Rong",
                                "start": "08:00", "end": "09:00"}]}
        bad = sweep(itin, [], SNAPSHOT)
        self.assertTrue(any("ten sai" in b for b in bad))

    def test_invented_hours_caught(self):
        exp = [{"claim": "musu mo cua 18:00-22:00", "facts": ["nghe noi"],
                "inference": "", "inference_marked": False, "uncertainty": [],
                "source": "x", "verified": True}]
        bad = sweep(CLEAN_ITIN, exp, SNAPSHOT)
        self.assertTrue(any("gio tu che: 18:00-22:00" in b for b in bad))


if __name__ == "__main__":
    unittest.main()
