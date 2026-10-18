"""Route matrix service (T010, lane B). Cache-first, OSRM backfill, no haversine.

- CACHE FIRST: loads `matrix.json` from the snapshot dir
  (default `data/snapshots/danang-v1/`); every feasibility decision
  uses cached/OSRM minutes.
- PER-CELL SOURCE: a cell may carry its own `source`; otherwise the
  file-level `source` applies (legacy seed files: `"cache"`). Matrix
  builds label OSRM cells `"osrm"` and any legacy haversine seed cell
  `"haversine_seed"` so low-confidence data is never mistaken for OSRM.
- OSRM BACKFILL (T010b): pass `osrm_base_url` + `coords`
  (`poi_id -> (lat, lon)`) to resolve a cache miss live via the OSRM
  table service (`BE/app/services/osrm_client.py`). `osrm_client=` is
  injectable for tests. Without backfill wiring a miss stays loud.
- NEVER haversine-only for feasibility (research R4: haversine breaks
  B3 feasibility). This module contains NO haversine code by design —
  a miss is a loud `MatrixMissError` or `(None, "infeasible")` from
  `minutes_or_none()`, never a silent 0 or an estimate.

Served to the optimizer (T017) via `minutes(a, b)` and `travel_fit()`.
"""

from __future__ import annotations

import json
import os

from BE.app.services.osrm_client import OsrmClient, OsrmTableError

ROW_SEP = "->"


class MatrixMissError(KeyError):
    """Cache miss with no OSRM backfill configured — fail loud, never guess."""


class MatrixService:
    def __init__(self, snapshot_dir: str = os.path.join("data", "snapshots", "danang-v1"),
                 osrm_base_url: str = "", coords: dict | None = None,
                 osrm_client: OsrmClient | None = None):
        self.snapshot_dir = snapshot_dir
        self.osrm_base_url = (osrm_base_url or "").rstrip("/")
        self.coords: dict = dict(coords or {})
        self._client = osrm_client  # tests inject; else built lazily on first miss
        self._backfill: dict[str, tuple[int, str]] = {}
        with open(os.path.join(snapshot_dir, "matrix.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.ids: list[str] = data["ids"]
        self.cells: dict = data["cells"]
        self.source: str = data.get("source", "cache")

    # -- cache-first reads ---------------------------------------------------

    def minutes(self, a: str, b: str) -> tuple[int, str]:
        """(minutes, source). Cache hit, else OSRM backfill, else raise."""
        if a == b:
            return 0, "cache"
        cell = self.cells.get(f"{a}{ROW_SEP}{b}")
        if cell is not None:
            return int(cell["minutes"]), cell.get("source", self.source)
        hit = self._backfill.get(f"{a}{ROW_SEP}{b}")
        if hit is not None:
            return hit
        if self.osrm_base_url:
            return self.fetch_osrm(a, b)
        raise MatrixMissError(f"no cached cell {a}->{b} (snapshot {self.snapshot_dir})")

    def minutes_or_none(self, a: str, b: str) -> tuple[int | None, str]:
        """None-safe read for consumers that encode infeasible as None (B3).

        Returns `(None, "infeasible")` instead of raising; never 0-on-miss.
        """
        try:
            return self.minutes(a, b)
        except (MatrixMissError, RuntimeError):
            return None, "infeasible"

    def travel_fit(self, a: str, b: str, gap_min: int) -> bool:
        """True iff the cached/OSRM travel minutes fit the time gap."""
        need, _ = self.minutes(a, b)
        return gap_min >= need

    # -- OSRM backfill (T010b) -----------------------------------------------

    def fetch_osrm(self, a: str, b: str) -> tuple[int, str]:
        """Resolve one pair via the OSRM table service; never guesses.

        RuntimeError when backfill is not wired (no base_url/coords),
        MatrixMissError when OSRM cannot route the pair (infeasible, B3).
        """
        if not self.osrm_base_url:
            raise RuntimeError("fetch_osrm needs osrm_base_url")
        pa, pb = self.coords.get(a), self.coords.get(b)
        if pa is None or pb is None:
            raise RuntimeError("fetch_osrm needs coords wiring (T008 snapshot loader)")
        client = self._client
        if client is None:
            client = self._client = OsrmClient(self.osrm_base_url)
        try:
            cells, _stats = client.table([(a, pa[0], pa[1]), (b, pb[0], pb[1])])
        except OsrmTableError as exc:
            raise MatrixMissError(f"OSRM failed for {a}->{b}: {exc}") from exc
        cell = cells.get((a, b))
        if cell is None:
            raise MatrixMissError(f"OSRM cannot route {a}->{b} (infeasible, B3)")
        hit = (int(cell["minutes"]), cell.get("source", "osrm"))
        self._backfill[f"{a}{ROW_SEP}{b}"] = hit
        return hit
