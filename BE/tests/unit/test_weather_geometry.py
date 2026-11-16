"""Unit tests for T063 OSM geometry fetching (no network access).

Run from repo root::

    python -m unittest BE.tests.unit.test_weather_geometry -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.weather_label import fetch_geometry as geom  # noqa: E402
from BE.ml.weather_label.labeler import classify_poi  # noqa: E402

POLY = [
    {"lat": 15.99, "lon": 107.99},
    {"lat": 15.99, "lon": 108.01},
    {"lat": 16.01, "lon": 108.01},
    {"lat": 16.01, "lon": 107.99},
    {"lat": 15.99, "lon": 107.99},
]
FAR_POLY = [
    {"lat": 16.19, "lon": 108.19},
    {"lat": 16.19, "lon": 108.21},
    {"lat": 16.21, "lon": 108.21},
    {"lat": 16.21, "lon": 108.19},
    {"lat": 16.19, "lon": 108.19},
]
POI = {"poi_id": "a", "lat": 16.0, "lon": 108.0, "name": "Bảo tàng Chăm"}


def way(element_id: int, tags: dict, geometry=None) -> dict:
    element = {"type": "way", "id": element_id, "tags": tags}
    if geometry is not None:
        element["geometry"] = geometry
    return element


def response(*elements: dict) -> dict:
    return {"elements": list(elements)}


class FakeTransport:
    def __init__(self, payloads=None, fail_endpoints=()):
        self.payloads = payloads if payloads is not None else [response()]
        self.fail_endpoints = set(fail_endpoints)
        self.calls: list[tuple[str, str, float]] = []
        self.index = 0

    def __call__(self, endpoint: str, query: str, timeout: float) -> dict:
        self.calls.append((endpoint, query, timeout))
        if endpoint in self.fail_endpoints:
            raise RuntimeError(f"{endpoint} unavailable")
        payload = self.payloads[min(self.index, len(self.payloads) - 1)]
        self.index += 1
        return payload


def fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


class TestQuery(unittest.TestCase):
    def test_query_has_tag_filters_and_geometry_output(self):
        query = geom.build_query([(16.0, 108.0), (16.1, 108.1)],
                                 radius=75, timeout=90)
        for key in geom.RELEVANT_KEYS:
            self.assertIn(key, query, key)
        self.assertIn("weather_shelter", query)
        self.assertIn("out center geom tags;", query)
        self.assertIn("[out:json][timeout:90];", query)
        self.assertIn("around:75,16,108", query)
        self.assertIn("around:75,16.1,108.1", query)
        self.assertIn("way(", query)
        self.assertIn("relation(", query)
        # 4 clauses per point (way/relation x key/amenity).
        self.assertEqual(query.count("around:"), 8)


class TestBatching(unittest.TestCase):
    def test_batches_and_sleeps_between_requests(self):
        rows = [{"poi_id": i, "lat": 16.0 + i * 0.001, "lon": 108.0,
                 "name": f"POI {i}"} for i in range(25)]
        transport = FakeTransport()
        sleeps: list[float] = []

        result = geom.fetch_geometry(
            rows, transport=transport, sleep=sleeps.append,
            batch_size=20, radius=60, timeout=30, delay=0.5, now=fixed_now)

        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(sleeps, [0.5])
        first, second = transport.calls[0][1], transport.calls[1][1]
        self.assertEqual(first.count("around:"), 20 * 4)
        self.assertEqual(second.count("around:"), 5 * 4)
        self.assertIn("around:60,", first)
        self.assertEqual(len(result["by_poi"]), 25)
        self.assertEqual(transport.calls[0][2], 30)

    def test_unqueryable_rows_get_empty_buckets(self):
        rows = [POI, {"poi_id": "bad", "name": "No coords"}]
        transport = FakeTransport()

        result = geom.fetch_geometry(rows, transport=transport,
                                     sleep=lambda _: None, now=fixed_now)

        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0][1].count("around:"), 4)
        self.assertEqual(result["by_poi"]["bad"], [])
        self.assertIn("a", result["by_poi"])

    def test_no_transport_call_for_empty_input(self):
        transport = FakeTransport()
        result = geom.fetch_geometry([], transport=transport,
                                     sleep=lambda _: None, now=fixed_now)
        self.assertEqual(transport.calls, [])
        self.assertEqual(result["by_poi"], {})
        self.assertEqual(result["source"], geom.PRIMARY_ENDPOINT)


class TestAssociation(unittest.TestCase):
    def test_only_linked_or_containing_geometry_is_included(self):
        elements = [
            way(1, {"building": "yes"}, POLY),                    # contains
            way(2, {"tourism": "museum", "name": "Bảo tàng Chăm"},
                FAR_POLY),                                        # name link
            way(3, {"building": "yes"}, FAR_POLY),                # nearby, no link
            way(4, {"amenity": "cafe"}, FAR_POLY),                # irrelevant
            {"type": "node", "id": 5, "lat": 16.0, "lon": 108.0,
             "tags": {"building": "yes"}},                        # node
            {"type": "way", "id": 6, "tags": {"building": "yes"},
             "center": {"lat": 16.0, "lon": 108.0}},              # center only
            {"type": "way", "id": 7, "tags": {"building": "yes"},
             "geometry": POLY[:3]},                               # open line
        ]
        transport = FakeTransport([response(*elements)])
        result = geom.fetch_geometry([POI], transport=transport,
                                     sleep=lambda _: None, now=fixed_now)

        ids = [element["id"] for element in result["by_poi"]["a"]]
        self.assertEqual(ids, [1, 2])

    def test_no_match_returns_empty_list(self):
        transport = FakeTransport([response(way(1, {"building": "yes"}, FAR_POLY))])
        result = geom.fetch_geometry([POI], transport=transport,
                                     sleep=lambda _: None, now=fixed_now)
        self.assertEqual(result["by_poi"]["a"], [])

    def test_same_element_maps_to_each_containing_poi(self):
        rows = [POI, {"poi_id": "b", "lat": 16.005, "lon": 108.005,
                      "name": "Another"}]
        transport = FakeTransport([response(way(1, {"building": "yes"}, POLY))])
        result = geom.fetch_geometry(rows, transport=transport,
                                     sleep=lambda _: None, now=fixed_now)
        self.assertEqual([e["id"] for e in result["by_poi"]["a"]], [1])
        self.assertEqual([e["id"] for e in result["by_poi"]["b"]], [1])

    def test_deduplicates_elements_within_a_bucket(self):
        element = way(1, {"building": "yes"}, POLY)
        transport = FakeTransport([response(element, element, element)])
        result = geom.fetch_geometry([POI], transport=transport,
                                     sleep=lambda _: None, now=fixed_now)
        self.assertEqual(len(result["by_poi"]["a"]), 1)

    def test_relation_member_ring_can_contain_poi(self):
        relation = {
            "type": "relation", "id": 9,
            "tags": {"building": "yes", "type": "multipolygon"},
            "members": [{"type": "way", "role": "outer", "geometry": POLY}],
        }
        transport = FakeTransport([response(relation)])
        result = geom.fetch_geometry([POI], transport=transport,
                                     sleep=lambda _: None, now=fixed_now)
        self.assertEqual([e["id"] for e in result["by_poi"]["a"]], [9])

    def test_output_is_accepted_by_the_labeler(self):
        transport = FakeTransport([response(way(1, {"building": "yes"}, POLY))])
        result = geom.fetch_geometry([POI], transport=transport,
                                     sleep=lambda _: None, now=fixed_now)
        classified = classify_poi(POI, osm=result["by_poi"]["a"])
        self.assertEqual((classified["space"], classified["space_source"]),
                         ("indoor", "osm"))
        self.assertEqual(classified["rain_protection"], "enclosed")


class TestEndpointsAndShape(unittest.TestCase):
    def test_mirror_fallback_when_primary_fails(self):
        transport = FakeTransport(fail_endpoints={geom.PRIMARY_ENDPOINT})
        result = geom.fetch_geometry([POI], transport=transport,
                                     sleep=lambda _: None, now=fixed_now)
        self.assertEqual([c[0] for c in transport.calls],
                         [geom.PRIMARY_ENDPOINT, geom.MIRROR_ENDPOINT])
        self.assertEqual(result["source"], geom.MIRROR_ENDPOINT)

    def test_all_endpoints_failing_raises(self):
        transport = FakeTransport(fail_endpoints=set(geom.ENDPOINTS))
        with self.assertRaises(RuntimeError):
            geom.fetch_geometry([POI], transport=transport,
                                sleep=lambda _: None, now=fixed_now)

    def test_output_shape_and_timestamp(self):
        transport = FakeTransport()
        result = geom.fetch_geometry([POI], transport=transport,
                                     sleep=lambda _: None, now=fixed_now)
        self.assertEqual(set(result), {"source", "fetched_at", "by_poi"})
        self.assertEqual(result["fetched_at"], "2026-01-02T03:04:05Z")
        self.assertIsInstance(result["by_poi"], dict)
        self.assertIsInstance(result["by_poi"]["a"], list)

    def test_no_network_when_transport_is_injected(self):
        transport = FakeTransport()
        with mock.patch("urllib.request.urlopen",
                        side_effect=AssertionError("network used")):
            result = geom.fetch_geometry([POI], transport=transport,
                                         sleep=lambda _: None, now=fixed_now)
        self.assertEqual(result["by_poi"]["a"], [])


class TestCli(unittest.TestCase):
    def test_cli_reads_input_and_writes_caller_output(self):
        payload = response(way(1, {"building": "yes"}, POLY))
        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "rows.json")
            output_path = os.path.join(tmp, "nested", "geometry.json")
            with open(input_path, "w", encoding="utf-8") as handle:
                json.dump([POI], handle)

            with mock.patch.object(geom, "default_transport",
                                   return_value=payload):
                code = geom.main(["--input", input_path, "--output",
                                  output_path, "--delay", "0"])

            self.assertEqual(code, 0)
            with open(output_path, encoding="utf-8") as handle:
                written = json.load(handle)
            self.assertEqual(set(written), {"source", "fetched_at", "by_poi"})
            self.assertEqual([e["id"] for e in written["by_poi"]["a"]], [1])

    def test_input_accepts_pois_wrapper(self):
        written = geom._prepare_rows({"pois": [POI]})
        self.assertEqual(written[0]["poi_id"], "a")
        self.assertTrue(written[0]["queryable"])

    def test_input_rejects_row_without_poi_id(self):
        with self.assertRaises(ValueError):
            geom._prepare_rows([{"lat": 16.0, "lon": 108.0, "name": "X"}])


if __name__ == "__main__":
    unittest.main()
