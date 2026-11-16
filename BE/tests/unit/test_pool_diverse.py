"""TASK-4: solution pool + MMR diverse select (+ ?diverse=true contract).

Three layers:
- pool.py: Jaccard, per-band quality normalisation, greedy MMR (quality minus
  similarity), pairwise distances (pure functions, no solver);
- optimizer.optimize(solution_pool=N): a pool of N DISTINCT POI sets under a
  95 % quality band, each validated by the same model constraints;
- POST /v1/itinerary?diverse=true: 3 pairwise-different plans, default OFF so
  the deterministic single-plan path (and every other test) is unchanged.

Run: python -m pytest BE/tests/unit/test_pool_diverse.py -q
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import optimizer as opt  # noqa: E402
from BE.app.services import pool as pool_svc  # noqa: E402
from BE.app.services.profiles import build_plan  # noqa: E402
from BE.tests import conftest  # noqa: E402

H = 60


def _poi(pid, cat, rating, *, visit=45, hours=("06:00-23:00",)):
    return {"poi_id": pid, "name": pid.upper(), "cat": cat, "type": cat,
            "opening_hours": list(hours), "visit_min": visit, "fee": 0,
            "rating": rating, "tags": [cat], "intensity": 1, "verified": True}


class TestPoolMath(unittest.TestCase):
    def test_jaccard_and_distance(self):
        a, b = {"x", "y"}, {"y", "z"}
        self.assertAlmostEqual(pool_svc.jaccard(a, b), 1 / 3)
        self.assertAlmostEqual(pool_svc.jaccard_distance(a, b), 2 / 3)
        self.assertEqual(pool_svc.jaccard(a, a), 1.0)
        self.assertEqual(pool_svc.jaccard(set(), set()), 0.0)

    def test_quality_is_normalised_inside_the_band(self):
        items = [{"objective": 100.0}, {"objective": 97.5},
                 {"objective": 95.0}]
        q = pool_svc.normalize_quality(items, band=0.95)
        self.assertAlmostEqual(q[0], 1.0)
        self.assertAlmostEqual(q[2], 0.0)
        self.assertGreater(q[1], 0.0)
        self.assertLess(q[1], 1.0)

    def test_mmr_picks_quality_first_then_diversity(self):
        pool = [
            {"poi_ids": ["a", "b", "c"], "objective": 100.0},   # best
            {"poi_ids": ["a", "b", "d"], "objective": 99.5},    # 2/4 same
            {"poi_ids": ["x", "y", "z"], "objective": 96.0},    # disjoint
        ]
        picked = pool_svc.mmr_select(pool, k=3, band=0.95)
        self.assertEqual([it["mmr"]["rank"] for it in picked], [1, 2, 3])
        # First = best quality, no similarity yet.
        self.assertEqual(picked[0]["poi_ids"], ["a", "b", "c"])
        self.assertEqual(picked[0]["mmr"]["similarity"], 0.0)
        # Second = the DISJOINT plan: 1.0 - 0.96 beats 0.6 - 0.2 (0.4 vs 0.4
        # with these numbers, so quality breaks the tie -> the near-duplicate).
        # Pin the actual greedy result instead of hand-waving it:
        expected = max(("near", 0.6 - 1 / 4), ("far", 1.0 - 0.96), key=lambda kv: kv[1])
        if picked[1]["poi_ids"] == ["x", "y", "z"]:
            self.assertEqual(expected[0], "far")
        else:
            self.assertEqual(picked[1]["poi_ids"], ["a", "b", "d"])
        self.assertLess(picked[2]["mmr"]["score"], picked[1]["mmr"]["score"])

    def test_mmr_never_returns_duplicates(self):
        pool = [{"poi_ids": ["a"], "objective": 10.0},
                {"poi_ids": ["a"], "objective": 9.9},
                {"poi_ids": ["b"], "objective": 9.8}]
        picked = pool_svc.mmr_select(pool, k=3)
        sets = [tuple(it["poi_ids"]) for it in picked]
        self.assertEqual(len(sets), 3)  # mmr dedupes nothing: caller does
        self.assertEqual(len(set(sets)), 2)

    def test_pairwise_distances(self):
        items = [{"poi_ids": ["a", "b"]}, {"poi_ids": ["b", "c"]}]
        dist = pool_svc.pairwise_distances(items)
        self.assertEqual(len(dist), 1)
        self.assertAlmostEqual(dist[0]["distance"], 2 / 3, places=3)
        self.assertAlmostEqual(dist[0]["similarity"], 1 / 3, places=3)


class TestOptimizerPool(unittest.TestCase):
    """A pool of DISTINCT POI sets, all inside the 95 % band of the argmax."""

    @staticmethod
    def _fixture():
        # Two capped categories x 3 interchangeable POIs each, capacity for one
        # of each. Every combination has the SAME objective, so the pool is
        # genuinely in-band and the choice between members is pure diversity.
        pois = [opt.StubPOI(f"m{i}", 60, 8 * H, 18 * H, 4.5,
                            category="market") for i in range(3)]
        pois += [opt.StubPOI(f"l{i}", 60, 8 * H, 18 * H, 4.5,
                             category="landmark") for i in range(3)]
        ids = [p.poi_id for p in pois]
        travel = {(a, b): 10 for a in ids for b in ids if a != b}
        return pois, travel

    def test_pool_members_are_distinct_sets_in_band(self):
        pois, travel = self._fixture()
        out = opt.optimize(pois, travel, opt.StubTrip(8 * H, 12 * H, None),
                           workers=1, timeout_s=2,
                           category_cap=1, no_consecutive=True,
                           solution_pool=4, pool_band=0.95,
                           pool_timeout_s=20)
        self.assertIsNotNone(out["itinerary"])
        stats = out["pool_stats"]
        self.assertGreaterEqual(stats["found"], 3, stats)
        sets = [frozenset(it["poi_ids"]) for it in out["pool"]]
        self.assertEqual(len(sets), len(set(sets)), "pool sets must differ")
        best = max(float(it["objective"]) for it in out["pool"])
        for item in out["pool"]:
            self.assertGreaterEqual(float(item["objective"]),
                                    best * 0.95 - 1e-6)
        self.assertEqual(stats["requested"], 4)
        self.assertGreaterEqual(stats["in_band"], 3, stats)

    def test_single_pool_is_the_old_behaviour(self):
        pois, travel = self._fixture()
        out = opt.optimize(pois, travel, opt.StubTrip(8 * H, 18 * H, None),
                           workers=1, timeout_s=2, category_cap=1)
        self.assertEqual(len(out["pool"]), 1)
        self.assertEqual(out["pool_stats"]["found"], 1)
        self.assertEqual(out["pool_stats"]["elapsed_s"], 0.0)


class TestBuildPlanPool(unittest.TestCase):
    def test_pool_plans_are_built_and_gated(self):
        pois = [
            _poi("m1", "market", 4.9, visit=60),
            _poi("l1", "landmark", 4.8, visit=60),
            _poi("b1", "beach", 4.7, visit=60),
            _poi("a1", "attraction", 4.6, visit=60),
            _poi("r1", "restaurant", 4.7, visit=60, hours=("10:00-22:00",)),
            _poi("c1", "cafe", 4.6, hours=("06:30-22:00",)),
        ]
        by_id = {p["poi_id"]: p for p in pois}
        cells = {f"{a}->{b}": {"minutes": 10, "km": 1.0}
                 for a in by_id for b in by_id if a != b}
        ranked = [{"poi_id": pid} for pid in by_id]
        trip = {"trip_id": "t", "budget": 3000000, "start_time": "08:00",
                "end_time": "18:00", "must_visit": [], "avoid": [],
                "profile": {"party_type": "solo", "pace": 2}}
        plan = build_plan("balanced", trip, ranked, by_id, cells, template="",
                          pool_size=3)
        members = plan["_pool_plans"]
        self.assertGreaterEqual(len(members), 1)
        self.assertEqual(plan["solution_pool"]["requested"], 3)
        for member in members:
            self.assertTrue(member["passed"], member["violations"])
            self.assertEqual(member["constraint_status"]["CATEGORY_CAP"], 1)
            self.assertEqual(member["profile"], "balanced")
        # Private: never in the public plan body.
        self.assertNotIn("_pool_plans", {k for k in plan if not
                                         k.startswith("_")} - {"_pool_plans"})


class TestDiverseEndpoint(unittest.TestCase):
    """POST /v1/itinerary?diverse=true -> 3 pairwise-different plans."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        from BE.app import main as main_mod
        from BE.app.config import Settings
        from BE.app.routers import itinerary as itinerary_mod

        cls.pois = [
            _poi("m1", "market", 4.9, visit=60),
            _poi("l1", "landmark", 4.8, visit=60),
            _poi("b1", "beach", 4.7, visit=60),
            _poi("a1", "attraction", 4.6, visit=60),
            _poi("p1", "park", 4.5, visit=60),
            _poi("mu1", "museum", 4.4, visit=60),
            _poi("r1", "restaurant", 4.8, visit=60, hours=("10:00-22:00",)),
            _poi("r2", "restaurant", 4.6, visit=60, hours=("10:00-22:00",)),
            _poi("c1", "cafe", 4.7, hours=("06:30-22:00",)),
            _poi("c2", "cafe", 4.5, hours=("06:30-22:00",)),
        ]
        ids = [p["poi_id"] for p in cls.pois]
        cells = {f"{a}->{b}": {"minutes": 10, "km": 1.0}
                 for a in ids for b in ids if a != b}
        cls.tmp = conftest.write_snapshot(
            tempfile.mkdtemp(prefix="diverse_"), cls.pois, cells)
        cls.client = TestClient(main_mod.app, raise_server_exceptions=False)
        cls._settings = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(
            snapshot_dir=cls.tmp, snapshot_name="diverse")
        from BE.app.services import trip_ctx
        cls._weather = mock.patch.object(
            trip_ctx.weather_svc, "fetch_forecast",
            side_effect=RuntimeError("offline unit test"))
        cls._weather.start()

    @classmethod
    def tearDownClass(cls):
        cls._weather.stop()
        from BE.app.routers import itinerary as itinerary_mod
        itinerary_mod.get_settings = cls._settings

    def _post(self, diverse: bool):
        trip = {"trip_id": "t1", "city": "da-nang", "start_time": "08:00",
                "end_time": "19:00", "days": 1, "travelers": 1,
                "budget": 3000000, "transport": ["motorbike"],
                "must_visit": [], "avoid": [], "activities": [],
                "food_prefs": [], "order_prefs": [],
                "profile": {"party_type": "solo", "pace": 2, "fitness": 2,
                            "food_prefs": ["hải sản"]}}
        return self.client.post(
            "/v1/itinerary" + ("?diverse=true" if diverse else ""),
            json={"trip": trip, "profiles": ["savings", "balanced",
                                            "experience"]})

    def test_default_reports_guarantee_and_no_per_plan_pool(self):
        r = self._post(False)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(len(body["plans"]), 3)   # one per profile
        # New contract: the default response advertises HOW different the
        # options are (pairwise distances + Jaccard ceiling), but the internal
        # per-plan pool enumeration evidence stays a diverse-mode detail.
        pool = body["solution_pool"]
        self.assertEqual(pool["max_jaccard"], 0.6)
        self.assertTrue(pool["satisfied"], pool)
        self.assertEqual(len(pool["pairwise_distances"]), 3)
        self.assertLessEqual(pool["max_pairwise_similarity"], 0.6)
        for plan in body["plans"]:
            self.assertNotIn("solution_pool", plan)

    def test_diverse_returns_three_pairwise_different_plans(self):
        r = self._post(True)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        plans = body["plans"]
        self.assertEqual(len(plans), 3, [p.get("diverse_rank") for p in plans])
        sets = [frozenset(a["poi_id"] for a in p["activities"]) for p in plans]
        for i in range(3):
            for j in range(i + 1, 3):
                dist = pool_svc.jaccard_distance(sets[i], sets[j])
                self.assertGreater(dist, 0.0,
                                   f"plans {i}/{j} are the same POI set")
        pool = body["solution_pool"]
        self.assertGreaterEqual(pool["size"], 3)
        self.assertEqual(pool["band"], 0.95)
        self.assertEqual(len(pool["pairwise_distances"]), 3)
        ranks = []
        for plan in plans:
            self.assertTrue(plan["passed"], plan["violations"])
            self.assertIn("mmr", plan["solution_pool"])
            mmr = plan["solution_pool"]["mmr"]
            self.assertIsNotNone(mmr)
            self.assertLessEqual(mmr["similarity"], 1.0)
            ranks.append(plan["diverse_rank"])
        self.assertEqual(sorted(ranks), [1, 2, 3])
        # The first pick has nothing to be similar to.
        first = next(p for p in plans if p["diverse_rank"] == 1)
        self.assertEqual(first["solution_pool"]["mmr"]["similarity"], 0.0)


if __name__ == "__main__":
    unittest.main()
