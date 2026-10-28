"""Contract tests for POST /v1/itinerary and the select registration seam.

Candidates are built from the real retrieval service against a temporary
snapshot. The lane-B profile planner is absent on this branch, so the API
must return an explicit 501 rather than a rank-order stub.
"""

import os
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.routers import select as select_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402
from BE.app.services import retrieval as retrieval_svc  # noqa: E402
from BE.tests import conftest  # noqa: E402

POIS = [
    {"poi_id": "beach", "name": "Beach", "type": "beach", "lat": 16.0,
     "lon": 108.2, "opening_hours": ["00:00-23:59"],
     "visit_min": {"p25": 60, "p50": 90, "p75": 120}, "dur_source": "category_rule",
     "dur_confidence": "low", "price_level": 1, "fee": 0, "rating": 4.6,
     "tags": ["biển"], "intensity": 2, "ambience": "", "weather_sensitive": True,
     "pros": [], "cons": [], "source": "t", "fetched_at": "2026-09-28", "verified": True},
    {"poi_id": "noodle", "name": "Noodle", "type": "restaurant", "lat": 16.0,
     "lon": 108.2, "opening_hours": ["07:00-21:00"],
     "visit_min": {"p25": 30, "p50": 60, "p75": 90}, "dur_source": "category_rule",
     "dur_confidence": "low", "price_level": 2, "fee": 50000, "rating": 4.5,
     "tags": ["ăn"], "intensity": 1, "ambience": "", "weather_sensitive": False,
     "pros": [], "cons": [], "source": "t", "fetched_at": "2026-09-28", "verified": True},
]
CELLS = {"beach->noodle": {"minutes": 10, "km": 3.0},
         "noodle->beach": {"minutes": 10, "km": 3.0}}
TRIP = {"trip_id": "t1", "user_id": "u1", "city": "da-nang",
        "start_time": "07:00", "end_time": "18:00", "days": 1,
        "travelers": 2, "budget": 3000000, "transport": ["motorbike"],
        "must_visit": [], "avoid": [], "activities": ["biển", "ăn"],
        "food_prefs": [], "order_prefs": []}

client = TestClient(main_mod.app, raise_server_exceptions=False)


def _collect_post_paths(routes, prefix="", seen=None):
    """Collect POST paths from an app/routes tree, version-agnostically.

    Older FastAPI/Starlette flatten included routers into ``app.routes`` as
    ``Route`` objects with a concrete ``path``/``methods``. Newer versions
    (FastAPI>=0.146 / Starlette 1.9) keep them lazy as ``_IncludedRouter``
    entries where ``path``/``methods`` are ``None`` and the real routes live on
    ``.original_router.routes`` (with the include prefix on
    ``.include_context.prefix``). Recurse through both shapes so the assertion
    keeps checking "a POST route exists" regardless of version.
    """
    if seen is None:
        seen = set()
    paths = set()
    for route in routes:
        if id(route) in seen:
            continue
        seen.add(id(route))

        original = getattr(route, "original_router", None)
        if original is not None:
            ctx = getattr(route, "include_context", None)
            nested_prefix = prefix + (getattr(ctx, "prefix", "") or "")
            paths |= _collect_post_paths(
                getattr(original, "routes", []), nested_prefix, seen)

        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path and "POST" in methods:
            paths.add(prefix + path)

        nested = getattr(route, "routes", None)
        if nested:
            paths |= _collect_post_paths(nested, prefix, seen)
    return paths


class TestItineraryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = conftest.write_snapshot(
            tempfile.mkdtemp(prefix="snap_"), POIS, CELLS)
        cls._real = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir=cls.tmp,
                                                      snapshot_name="test")

    @classmethod
    def tearDownClass(cls):
        itinerary_mod.get_settings = cls._real

    def _retrieval_pool(self):
        pois = retrieval_svc.load_pois_json(os.path.join(self.tmp, "pois.json"))
        return retrieval_svc.retrieve(TRIP, pois)["candidates"]

    def test_itinerary_router_registered(self):
        post_paths = _collect_post_paths(main_mod.app.routes)
        if not post_paths:
            # Defensive fallback for shapes we cannot walk directly.
            post_paths = {
                path for path, ops in main_mod.app.openapi().get("paths", {}).items()
                if "post" in ops
            }
        self.assertIn("/v1/itinerary", post_paths)
        self.assertIn("/v1/itinerary/select", post_paths)

    def test_three_profiles_yield_three_plans_or_501(self):
        pool = self._retrieval_pool()
        self.assertEqual({candidate["poi_id"] for candidate in pool},
                         {"beach", "noodle"})

        profiles = ["savings", "balanced", "experience"]
        r = client.post("/v1/itinerary", json={"trip": TRIP, "profiles": profiles})
        if r.status_code == 501:
            body = r.json()
            self.assertEqual(set(body), {"error", "message"})
            self.assertEqual(body["error"], "PLANNER_UNAVAILABLE")
            return

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIsNone(body["selected"])
        self.assertEqual([plan["profile"] for plan in body["plans"]], profiles)
        self.assertEqual(len({plan["itinerary_id"] for plan in body["plans"]}), 3)

    def test_default_profiles_are_three_structural_objectives(self):
        """Omitting `profiles` must return savings+balanced+experience."""
        from BE.app.routers.itinerary import ItineraryIn
        from BE.app.schemas.trip import TripRequest

        self.assertEqual(
            ItineraryIn(trip=TripRequest(**TRIP)).profiles,
            ["savings", "balanced", "experience"])

        built_profiles = []

        def build_plan(**kwargs):
            built_profiles.append(kwargs["profile"])
            return {"activities": [], "total_cost": 0, "total_km": 0,
                    "total_min": 0, "constraint_status": {}}

        old_builder = itinerary_mod._get_plan_builder
        try:
            itinerary_mod._get_plan_builder = lambda: build_plan
            r = client.post("/v1/itinerary", json={"trip": TRIP})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(built_profiles,
                             ["savings", "balanced", "experience"])
            plans = r.json()["plans"]
            self.assertEqual([p["profile"] for p in plans],
                             ["savings", "balanced", "experience"])
        finally:
            itinerary_mod._get_plan_builder = old_builder

    def test_itinerary_id_not_hardcoded(self):
        trip_id = "request-trip-uuid-test"
        requested_profiles = ["savings", "balanced", "experience"]
        built_profiles = []

        def build_plan(**kwargs):
            built_profiles.append(kwargs["profile"])
            return {"activities": [], "total_cost": 0, "total_km": 0,
                    "total_min": 0, "constraint_status": {}}

        store = select_mod.get_store()
        old_plans = dict(store["plans"])
        old_active_id = store["active_id"]
        old_selected = store["selected"]
        old_builder = itinerary_mod._get_plan_builder
        try:
            select_mod.reset_store()
            itinerary_mod._get_plan_builder = lambda: build_plan
            r = client.post("/v1/itinerary", json={
                "trip": dict(TRIP, trip_id=trip_id),
                "profiles": requested_profiles,
            })
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(built_profiles, requested_profiles)
            plans = r.json()["plans"]
            self.assertEqual([plan["profile"] for plan in plans], requested_profiles)
            self.assertEqual(len(plans), len(requested_profiles))
            itinerary_ids = set()
            for plan in plans:
                self.assertEqual(plan["trip_id"], trip_id)
                self.assertNotEqual(plan["itinerary_id"], "it-stub-1")
                uuid.UUID(plan["itinerary_id"])
                itinerary_ids.add(plan["itinerary_id"])
            self.assertEqual(len(itinerary_ids), len(requested_profiles))
            self.assertTrue(itinerary_ids.issubset(select_mod.get_store()["plans"]))

            selected = client.post("/v1/itinerary/select", json={
                "itinerary_id": plans[0]["itinerary_id"]})
            self.assertEqual(selected.status_code, 200, selected.text)
            self.assertEqual(selected.json(), {"active_id": plans[0]["itinerary_id"]})
        finally:
            itinerary_mod._get_plan_builder = old_builder
            store["plans"] = old_plans
            store["active_id"] = old_active_id
            store["selected"] = old_selected

    def test_get_itinerary_returns_public_plan(self):
        """GET /v1/itinerary/{id}: same public shape POST returns (no _keys)."""
        select_mod.reset_store()
        plan = {"itinerary_id": "it-get", "profile": "balanced",
                "trip_id": "t1",
                "activities": [{"poi_id": "beach", "start": "08:00",
                                "end": "10:00"}],
                "total_cost": 0,
                "_context": {"trip": TRIP, "pois": ["beach"], "travel": {}}}
        try:
            select_mod.register([plan])
            r = client.get("/v1/itinerary/it-get")
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            self.assertEqual(body, {k: v for k, v in plan.items()
                                    if not k.startswith("_")})
            self.assertNotIn("_context", body)
        finally:
            select_mod.reset_store()

    def test_get_unknown_itinerary_404_envelope(self):
        select_mod.reset_store()
        r = client.get("/v1/itinerary/it-ghost")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(set(r.json()), {"error", "message"})
        self.assertEqual(r.json()["error"], "UNKNOWN_ITINERARY")

    def test_missing_snapshot_envelope(self):
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir="/no/such/dir",
                                                      snapshot_name="x")
        try:
            r = client.post("/v1/itinerary", json={"trip": TRIP})
        finally:
            itinerary_mod.get_settings = lambda: Settings(snapshot_dir=self.tmp,
                                                          snapshot_name="test")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(set(r.json()), {"error", "message"})
        self.assertEqual(r.json()["error"], "SNAPSHOT_MISSING")


if __name__ == "__main__":
    unittest.main()
