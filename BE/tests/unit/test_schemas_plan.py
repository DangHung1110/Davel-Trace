"""Unit test for plan schemas (T007-plan). Stdlib runner + pydantic.

Run from repo root: python BE/tests/unit/test_schemas_plan.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from pydantic import ValidationError  # noqa: E402

from BE.app.schemas.plan import Activity, Itinerary, RouteSegment  # noqa: E402


def good_itinerary() -> dict:
    return {
        "itinerary_id": "it1", "trip_id": "t1", "version": 1,
        "activities": [
            {"poi_id": "son-tra", "start": "07:30", "end": "11:24",
             "intensity": 3, "visit_min": 234},
            {"poi_id": "my-khe", "start": "12:00", "end": "14:24",
             "visit_min": 144},
        ],
        "segments": [{"from_id": "son-tra", "to_id": "my-khe",
                      "km": 8.5, "minutes": 17, "source": "cache"}],
        "total_cost": 0, "total_km": 8.5, "total_min": 378,
        "constraint_status": {"FAR": 0, "BCS": 1},
    }


class TestSchemasPlan(unittest.TestCase):
    def test_valid_itinerary(self):
        it = Itinerary(**good_itinerary())
        self.assertEqual(len(it.activities), 2)
        self.assertEqual(it.segments[0].minutes, 17)
        print(f"\n itinerary OK: {it.itinerary_id} v{it.version}")

    def test_missing_activities_errors(self):
        bad = good_itinerary()
        del bad["activities"]
        with self.assertRaises(ValidationError):
            Itinerary(**bad)

    def test_segments_count_mismatch_errors(self):
        bad = good_itinerary()
        bad["segments"] = [{"from_id": "a", "to_id": "b", "km": 1, "minutes": 2},
                           {"from_id": "b", "to_id": "c", "km": 1, "minutes": 2}]
        with self.assertRaises(ValidationError):
            Itinerary(**bad)

    def test_bad_status_errors(self):
        with self.assertRaises(ValidationError):
            Activity(poi_id="x", start="08:00", end="09:00", visit_min=60,
                     status="flying")

    def test_segment_source_vocab(self):
        with self.assertRaises(ValidationError):
            RouteSegment(from_id="a", to_id="b", km=1, minutes=2, source="guess")


if __name__ == "__main__":
    unittest.main()
