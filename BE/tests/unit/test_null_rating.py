"""Regression: a POI with rating=null must not break plan building.

Live smoke test caught POST /v1/itinerary -> 500 on the 7-POI seed because
`danang-airport` carries `rating: null`, and plan building did
`float(pois[...].get("rating", 0))` -> float(None) -> TypeError.
"""

from __future__ import annotations

import unittest

from BE.app.services import profiles, response

POIS = {
    "null-rating": {"poi_id": "null-rating", "name": "San bay", "rating": None,
                    "fee": 0, "visit_min": {"p50": 30},
                    "opening_hours": ["00:00-23:59"]},
    "rated": {"poi_id": "rated", "name": "Bien", "rating": 4.6,
              "fee": 0, "visit_min": {"p50": 60},
              "opening_hours": ["05:00-18:00"]},
}
ACTS = [
    {"poi_id": "null-rating", "start": "07:00", "end": "07:30",
     "explanation": {"evidence": ["x"]}},
    {"poi_id": "rated", "start": "08:00", "end": "09:00",
     "explanation": {"evidence": ["x"]}},
]
TRIP = {"trip_id": "t1", "city": "da-nang", "budget": 3000000,
        "start_time": "07:00", "end_time": "18:00"}


class TestNullRating(unittest.TestCase):
    def test_build_plan_tolerates_null_rating(self):
        plan = response.build_plan(
            {"itinerary": {"activities": [dict(a) for a in ACTS]}},
            {"passed": True, "checks": {}},
            TRIP, POIS, {},
        )
        # 0.0 for the null-rated POI, 4.6 for the rated one -> mean 2.3
        self.assertAlmostEqual(plan["preference"], 2.3, places=3)
        self.assertEqual(len(plan["activities"]), 2)

    def test_score_plan_tolerates_null_rating(self):
        plan = {"itinerary_id": "p1", "activities": [dict(a) for a in ACTS],
                "total_cost": 0, "total_min": 120}
        scores = profiles.score_plan(plan)
        self.assertIsInstance(scores, dict)
        self.assertIn("profit", scores)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
