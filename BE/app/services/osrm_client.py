"""OSRM table client (T010b, lane B). Stdlib urllib, batched `/table/v1/driving/`.

- INPUT: `points = [(poi_id, lat, lon), ...]` in matrix order.
- OUTPUT: `(cells, stats)`:
    cells[(a_id, b_id)] = {"km": float, "minutes": int, "source": "osrm"}
    stats = {"requests", "ok_requests", "failed_requests", "failed_shards",
             "cells", "missing", "missing_pairs", "last_error", "elapsed_s"}
- NEVER estimates: a pair OSRM cannot route (null duration) is MISSING from
  `cells` — consumers treat a miss as infeasible (B3), never as 0.
- BATCHING: sources are chunked (`chunk`, default 100 = osrm-routed's default
  `--max-table-size`); destinations stay "all" so response row/column indices
  map 1:1 to the input point order.
- distance annotation = route metres; minutes = seconds rounded, min 1 for a
  distinct pair (a routed leg must not collapse to a silent 0).
"""

from __future__ import annotations

import json
import time
import urllib.request


class OsrmTableError(RuntimeError):
    """Network/JSON failure or non-Ok OSRM response (after retries)."""


def _http_get_json(url: str, timeout_s: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _round_minutes(seconds: float, *, same: bool) -> int:
    if same:
        return 0
    return max(1, int(seconds / 60.0 + 0.5))


class OsrmClient:
    """Minimal OSRM `/table` client; `transport` is injectable for tests."""

    def __init__(self, base_url: str, *, timeout_s: float = 30.0, chunk: int = 100,
                 retries: int = 1, transport=None, wait=None):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.chunk = max(1, int(chunk))
        self.retries = max(0, int(retries))
        self._transport = transport or _http_get_json
        self._wait = wait or time.sleep

    # -- internals ---------------------------------------------------------

    def _request(self, url: str) -> dict:
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return self._transport(url, self.timeout_s)
            except Exception as exc:  # noqa: BLE001 — retried, then wrapped
                last = exc
                if attempt < self.retries:
                    self._wait(1.0)
        raise OsrmTableError(f"OSRM request failed after {self.retries + 1} "
                             f"attempt(s): {last}")

    def _table_url(self, coord_str: str, sources: list[int]) -> str:
        return (f"{self.base_url}/table/v1/driving/{coord_str}"
                "?annotations=duration,distance&sources="
                + ";".join(str(i) for i in sources))

    def _count_missing(self, stats: dict, a_id: str, b_id: str) -> None:
        stats["missing"] += 1
        if len(stats["missing_pairs"]) < 200:
            stats["missing_pairs"].append([a_id, b_id])

    # -- public ------------------------------------------------------------

    def table(self, points: list[tuple[str, float, float]]) -> tuple[dict, dict]:
        """Query the OSRM table service for all `points` pairs.

        Returns `(cells, stats)`; unroutable/failed pairs are counted and
        omitted from `cells` (infeasible per B3 — never a silent 0).
        """
        t0 = time.monotonic()
        ids = [p[0] for p in points]
        coord_str = ";".join(f"{lon},{lat}" for _pid, lat, lon in points)
        cells: dict = {}
        stats = {"requests": 0, "ok_requests": 0, "failed_requests": 0,
                 "failed_shards": [], "cells": 0, "missing": 0,
                 "missing_pairs": [], "last_error": None, "elapsed_s": 0.0}

        for start in range(0, len(points), self.chunk):
            shard = list(range(start, min(start + self.chunk, len(points))))
            stats["requests"] += 1
            try:
                payload = self._request(self._table_url(coord_str, shard))
                if payload.get("code") != "Ok":
                    raise OsrmTableError(f"OSRM code={payload.get('code')!r} "
                                         f"message={payload.get('message')!r}")
                durations = payload.get("durations") or []
                distances = payload.get("distances") or []
                if len(durations) != len(shard):
                    raise OsrmTableError(f"durations rows {len(durations)} != "
                                         f"sources {len(shard)}")
            except OsrmTableError as exc:
                stats["failed_requests"] += 1
                stats["failed_shards"].append([start, shard[-1]])
                stats["last_error"] = str(exc)
                stats["missing"] += len(shard) * len(points)
                continue
            stats["ok_requests"] += 1
            for row_i, src_idx in enumerate(shard):
                row = durations[row_i]
                row_d = distances[row_i] if row_i < len(distances) else []
                if len(row) != len(points):
                    stats["missing"] += len(points)
                    stats["last_error"] = (f"row {src_idx} width {len(row)} != "
                                           f"{len(points)} destinations")
                    continue
                for dst_idx, sec in enumerate(row):
                    a_id, b_id = ids[src_idx], ids[dst_idx]
                    if sec is None:
                        self._count_missing(stats, a_id, b_id)
                        continue
                    km = 0.0
                    if dst_idx < len(row_d) and row_d[dst_idx] is not None:
                        km = round(float(row_d[dst_idx]) / 1000.0, 2)
                    cells[(a_id, b_id)] = {
                        "km": km,
                        "minutes": _round_minutes(float(sec), same=src_idx == dst_idx),
                        "source": "osrm",
                    }
        stats["cells"] = len(cells)
        stats["elapsed_s"] = round(time.monotonic() - t0, 3)
        return cells, stats
