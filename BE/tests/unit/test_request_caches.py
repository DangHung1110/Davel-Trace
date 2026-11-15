"""Per-request work that is now done once: the forecast memo, the parsed
pois.json, the dense travel read, and the bounded plan store.

Run: python -m pytest BE/tests/unit/test_request_caches.py -q
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.routers import select as select_mod  # noqa: E402
from BE.app.services import matrix as matrix_mod  # noqa: E402
from BE.app.services import retrieval  # noqa: E402
from BE.app.services import weather  # noqa: E402
from BE.app.services.matrix import DenseCells, travel_minutes  # noqa: E402

HOURS = [f"2026-10-03T{h:02d}:00" for h in range(24)]


def _forecast_payload():
    return {"hourly": {"time": HOURS, "temperature_2m": [30.0] * 24,
                       "precipitation_probability": [10] * 24}}


class TestForecastMemo(unittest.TestCase):
    def setUp(self):
        weather.clear_memo()
        self.cache = os.path.join(tempfile.mkdtemp(prefix="wxm_"), "w.json")

    def tearDown(self):
        weather.clear_memo()

    def test_a_fresh_forecast_is_fetched_once(self):
        calls = []

        def transport(url):
            calls.append(url)
            return _forecast_payload()

        first = weather.fetch_forecast(transport=transport, cache_path=self.cache)
        second = weather.fetch_forecast(transport=transport, cache_path=self.cache)
        self.assertEqual(len(calls), 1)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)  # callers may annotate their copy
        weather.clear_memo()
        weather.fetch_forecast(transport=transport, cache_path=self.cache)
        self.assertEqual(len(calls), 2)

    def test_a_failed_fetch_is_not_retried_at_once(self):
        calls = []

        def ok(url):
            return _forecast_payload()

        def down(url):
            calls.append(url)
            raise ConnectionError("no network")

        weather.fetch_forecast(transport=ok, cache_path=self.cache)  # fills the file cache
        stale = weather.fetch_forecast(transport=down, cache_path=self.cache)
        again = weather.fetch_forecast(transport=down, cache_path=self.cache)
        self.assertEqual(len(calls), 1)
        self.assertEqual((stale["source"], stale["stale"]), ("cache", True))
        self.assertEqual((again["source"], again["stale"]), ("cache", True))

    def test_transports_do_not_share_an_answer(self):
        def ok(url):
            return _forecast_payload()

        def down(url):
            raise ConnectionError("no network")

        weather.fetch_forecast(transport=ok, cache_path=self.cache)
        self.assertTrue(weather.fetch_forecast(transport=down, cache_path=self.cache)["stale"])


class TestPoisCache(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(prefix="pois_"), "pois.json")
        self._write([{"poi_id": "a"}])

    def _write(self, pois):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"pois": pois}, f)

    def test_parsed_once_per_file_version(self):
        first = retrieval.load_pois_json(self.path)
        self.assertIs(retrieval.load_pois_json(self.path), first)
        self._write([{"poi_id": "a"}, {"poi_id": "b"}])
        os.utime(self.path, ns=(1, 1))
        self.assertEqual([p["poi_id"] for p in retrieval.load_pois_json(self.path)], ["a", "b"])

    def test_missing_file_still_raises(self):
        with self.assertRaises(FileNotFoundError):
            retrieval.load_pois_json(os.path.join(os.path.dirname(self.path), "nope.json"))


class TestTravelMinutes(unittest.TestCase):
    IDS = ["a", "b", "c"]
    MINUTES = [[0, 5, None], [6, 0, 7], [8, 9, 0]]
    KM = [[0.0, 1.0, None], [1.2, 0.0, 1.4], [1.6, 1.8, 0.0]]

    def test_dense_rows_match_the_key_by_key_read(self):
        cells = DenseCells(self.IDS, self.MINUTES, self.KM)
        expect = {(a, b): cells[f"{a}->{b}"]["minutes"]
                  for a in self.IDS for b in self.IDS if a != b and f"{a}->{b}" in cells}
        self.assertEqual(travel_minutes(cells, self.IDS), expect)
        self.assertNotIn(("a", "c"), travel_minutes(cells, self.IDS))  # null stays absent

    def test_unknown_ids_and_legacy_cells(self):
        cells = DenseCells(self.IDS, self.MINUTES, self.KM)
        self.assertEqual(travel_minutes(cells, ["a", "ghost", "b"]), {("a", "b"): 5, ("b", "a"): 6})
        legacy = {"a->b": {"minutes": 5, "km": 1.0}, "b->a": {"minutes": 6, "km": 1.2}}
        self.assertEqual(travel_minutes(legacy, ["a", "b", "ghost"]), {("a", "b"): 5, ("b", "a"): 6})


class TestBoundedStore(unittest.TestCase):
    def setUp(self):
        select_mod.reset_store()
        self._cap = select_mod.MAX_STORED_PLANS
        select_mod.MAX_STORED_PLANS = 4

    def tearDown(self):
        select_mod.MAX_STORED_PLANS = self._cap
        select_mod.reset_store()

    def test_oldest_plans_leave_the_selected_one_stays(self):
        select_mod.register([{"itinerary_id": f"p{i}"} for i in range(4)])
        select_mod.get_store()["selected"] = "p0"
        select_mod.get_store()["active_id"] = "p0"
        select_mod.register([{"itinerary_id": "p4"}, {"itinerary_id": "p5"}])
        store = select_mod.get_store()["plans"]
        self.assertEqual(len(store), 4)
        self.assertEqual(list(store), ["p0", "p3", "p4", "p5"])

    def test_re_registering_an_id_is_not_a_second_entry(self):
        select_mod.register([{"itinerary_id": "p0"}, {"itinerary_id": "p0", "v": 2}])
        self.assertEqual(select_mod.get_store()["plans"]["p0"].get("v"), 2)
        self.assertEqual(len(select_mod.get_store()["plans"]), 1)


if __name__ == "__main__":
    unittest.main()
