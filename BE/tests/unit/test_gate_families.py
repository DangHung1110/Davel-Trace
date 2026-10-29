import unittest

from BE.app.services import gate


class TestGateFamilies(unittest.TestCase):
    def test_family_report_wraps_detailed_registry(self):
        itinerary = {
            "activities": [
                {"poi_id": "museum", "start": "08:00", "end": "09:00"},
            ]
        }
        trip = {
            "start_time": "07:00",
            "end_time": "18:00",
            "budget": 500_000,
            "must_visit": [],
            "avoid": [],
        }
        pois = {
            "museum": {
                "poi_id": "museum",
                "verified": True,
                "type": "museum",
                "fee": 20_000,
                "opening_hours": ["07:00-17:00"],
            }
        }

        report = gate.family_report(itinerary, trip, pois, {})

        self.assertEqual(
            list(report["families"]),
            [
                "temporal",
                "financial",
                "movement",
                "safety_data",
                "traveler_constraints",
            ],
        )
        self.assertTrue(report["passed"])
        self.assertEqual(report["failed_families"], [])
        detailed = {
            item["check"]
            for family in report["families"].values()
            for item in family["checks"]
        }
        self.assertTrue({"FAR", "VROH", "B3", "BCS", "ETB", "HCS"} <= detailed)

    def test_failed_family_retains_failed_detailed_check(self):
        itinerary = {
            "activities": [
                {"poi_id": "ghost", "start": "08:00", "end": "09:00"},
            ]
        }
        trip = {"start_time": "07:00", "end_time": "18:00", "budget": 0}

        report = gate.family_report(itinerary, trip, {}, {})

        self.assertFalse(report["passed"])
        self.assertIn("safety_data", report["failed_families"])
        far = next(
            item
            for item in report["families"]["safety_data"]["checks"]
            if item["check"] == "FAR"
        )
        self.assertFalse(far["passed"])


if __name__ == "__main__":
    unittest.main()
