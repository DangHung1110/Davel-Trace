"""Unit test for the OSRM table client (T010b). No Docker, no network.

Transport is injected: every test feeds canned OSRM payloads or raise
behaviours. Failure semantics asserted: unroutable pair -> MISSING cell
(infeasible, B3 — never a silent 0), failed requests counted, not silent.

Run from repo root: python BE/tests/unit/test_osrm_client.py -v
"""

import os
import sys
import unittest
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.osrm_client import OsrmClient, OsrmTableError  # noqa: E402

PTS = [("a", 16.00, 108.00), ("b", 16.10, 108.10), ("c", 16.20, 108.20)]


def payload_for(url: str, n_points: int, null_pairs=()) -> dict:
    """Canned /table payload derived from the URL's sources list."""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    sources = [int(s) for s in query["sources"][0].split(";")]
    durations, distances = [], []
    for i in sources:
        row, row_d = [], []
        for j in range(n_points):
            if (i, j) in null_pairs:
                row.append(None)
                row_d.append(None)
            else:
                row.append(float(i * 100 + j * 10))
                row_d.append(float((i + j) * 1000))
        durations.append(row)
        distances.append(row_d)
    return {"code": "Ok", "durations": durations, "distances": distances}


def transport_factory(n_points: int, null_pairs=(), fail_urls=(), fail_times=0):
    calls = {"n": 0, "urls": []}

    def transport(url, timeout_s):
        calls["n"] += 1
        calls["urls"].append(url)
        if any(tok in url for tok in fail_urls) or calls["n"] <= fail_times:
            raise OSError("connection refused")
        return payload_for(url, n_points, null_pairs)

    return transport, calls


class TestOsrmClient(unittest.TestCase):
    def client(self, transport, **kw):
        return OsrmClient("http://127.0.0.1:5000", transport=transport,
                          wait=lambda _s: None, **kw)

    def test_cells_km_minutes_source(self):
        transport, _ = transport_factory(2)
        cells, stats = self.client(transport).table(PTS[:2])
        self.assertEqual(stats["failed_requests"], 0)
        self.assertEqual(stats["cells"], 4)
        self.assertEqual(cells[("a", "b")],
                         {"km": 1.0, "minutes": 1, "source": "osrm"})  # 10 s
        self.assertEqual(cells[("b", "a")], {"km": 1.0, "minutes": 2, "source": "osrm"})
        self.assertEqual(cells[("a", "a")], {"km": 0.0, "minutes": 0, "source": "osrm"})

    def test_url_uses_lon_lat_order(self):
        transport, calls = transport_factory(1)
        self.client(transport).table(PTS[:1])
        self.assertIn("108.0,16.0", calls["urls"][0].split("?")[0])

    def test_distinct_pair_never_silent_zero(self):
        client = self.client(lambda url, t: {
            "code": "Ok", "durations": [[0.0, 0.0], [12.0, 0.0]],
            "distances": [[0.0, 0.0], [50.0, 0.0]]})
        cells, _ = client.table(PTS[:2])
        self.assertEqual(cells[("a", "b")]["minutes"], 1)   # 0 s -> floor 1 min
        self.assertEqual(cells[("b", "a")]["minutes"], 1)   # 12 s -> 1 min

    def test_null_duration_is_missing_not_zero(self):
        transport, _ = transport_factory(2, null_pairs={(0, 1)})
        cells, stats = self.client(transport).table(PTS[:2])
        self.assertNotIn(("a", "b"), cells)
        self.assertEqual(stats["missing"], 1)
        self.assertEqual(stats["missing_pairs"], [["a", "b"]])

    def test_batching_chunks_sources(self):
        transport, calls = transport_factory(3)
        cells, stats = self.client(transport, chunk=2).table(PTS)
        self.assertEqual(stats["requests"], 2)
        self.assertEqual(stats["ok_requests"], 2)
        self.assertTrue(calls["urls"][0].endswith("sources=0;1"))
        self.assertTrue(calls["urls"][1].endswith("sources=2"))
        self.assertEqual(len(cells), 9)

    def test_failed_request_counts_pairs_and_continues(self):
        transport, _ = transport_factory(3, fail_urls=("sources=0;1",))
        cells, stats = self.client(transport, chunk=2).table(PTS)
        self.assertEqual(stats["failed_requests"], 1)
        self.assertEqual(stats["failed_shards"], [[0, 1]])
        self.assertEqual(stats["missing"], 2 * 3)  # 2 sources x 3 dests
        self.assertEqual(len(cells), 3)  # shard sources=2 still routed
        self.assertIn("connection refused", stats["last_error"])

    def test_retry_then_success(self):
        transport, calls = transport_factory(2, fail_times=1)
        cells, stats = self.client(transport, retries=1).table(PTS[:2])
        self.assertEqual(stats["failed_requests"], 0)
        self.assertEqual(len(cells), 4)
        self.assertEqual(calls["n"], 2)

    def test_non_ok_code_is_failed_shard(self):
        client = self.client(lambda url, t: {"code": "NoSegment",
                                             "message": "no segment"})
        cells, stats = client.table(PTS[:2])
        self.assertEqual(cells, {})
        self.assertEqual(stats["failed_requests"], 1)
        self.assertEqual(stats["missing"], 4)
        self.assertIn("NoSegment", stats["last_error"])

    def test_row_width_mismatch_counts_missing(self):
        client = self.client(lambda url, t: {
            "code": "Ok",
            "durations": [[1.0, 2.0], [1.0, 2.0], [1.0, 2.0]],
            "distances": [[1.0, 2.0], [1.0, 2.0], [1.0, 2.0]]})
        cells, stats = client.table(PTS)  # 3 points, rows too narrow
        self.assertEqual(cells, {})
        self.assertEqual(stats["missing"], 9)
        self.assertIn("width", stats["last_error"])

    def test_request_error_raised_after_retries(self):
        def always_fail(url, timeout_s):
            raise OSError("boom")
        with self.assertRaises(OsrmTableError):
            self.client(always_fail, retries=1)._request("http://x/table")


if __name__ == "__main__":
    unittest.main()
