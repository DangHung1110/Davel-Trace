"""Route matrix service (T010, lane B). Cache-first, OSRM hook, no haversine.

- CACHE FIRST: loads `matrix.json` from the snapshot dir
  (default `data/snapshots/danang-v1/`); every feasibility decision
  uses cached/OSRM minutes.
- OSRM FETCH HOOK: `fetch_osrm()` (stdlib urllib, `/route/v1/driving/`)
  runs ONLY when `osrm_base_url` is configured (online backfill); the
  default offline mode raises `MatrixMissError` on a cache miss.
- NEVER haversine-only for feasibility (research R4: haversine breaks
  B3 feasibility). This module contains NO haversine code by design —
  a miss is a loud error, not a silent estimate.

Served to the optimizer (T017) via `minutes(a, b)` and `travel_fit()`.
"""

from __future__ import annotations

import json
import os
import urllib.request


class MatrixMissError(KeyError):
    """Cache miss with no OSRM backfill configured — fail loud, never guess."""


class MatrixService:
    def __init__(self, snapshot_dir: str = os.path.join("data", "snapshots", "danang-v1"),
                 osrm_base_url: str = ""):
        self.snapshot_dir = snapshot_dir
        self.osrm_base_url = osrm_base_url.rstrip("/")
        with open(os.path.join(snapshot_dir, "matrix.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.ids: list[str] = data["ids"]
        self.cells: dict = data["cells"]
        self.source: str = data.get("source", "cache")

    def minutes(self, a: str, b: str) -> tuple[int, str]:
        """(minutes, source). Cache hit, else OSRM backfill, else raise."""
        if a == b:
            return 0, "cache"
        cell = self.cells.get(f"{a}->{b}")
        if cell is not None:
            return int(cell["minutes"]), self.source
        if self.osrm_base_url:
            return self.fetch_osrm(a, b)
        raise MatrixMissError(f"no cached cell {a}->{b} (snapshot {self.snapshot_dir})")

    def travel_fit(self, a: str, b: str, gap_min: int) -> bool:
        """True iff the cached/OSRM travel minutes fit the time gap."""
        need, _ = self.minutes(a, b)
        return gap_min >= need

    def fetch_osrm(self, a: str, b: str) -> tuple[int, str]:
        """Online backfill hook (lane B later / full snapshot builds).

        Needs POI coords: override `coords(a)` when wiring the snapshot
        loader (T008). Raises RuntimeError when coords are unavailable.
        """
        raise RuntimeError("fetch_osrm needs coords wiring (T008 snapshot loader)")
