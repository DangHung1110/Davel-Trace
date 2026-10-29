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

- TWO FILE FORMATS, ONE VIEW (Phase 3): the legacy `cells` dict
  (`"a->b": {km, minutes[, source]}`) and the dense `dense-v1` format
  (`ids` + `minutes`/`km` row-major lists, `null` = unroutable). 742 POIs
  are 550k pairs: ~47 MB as `cells`, ~5 MB dense. `load_matrix_doc` /
  `load_cells` return `cells` as a read-only Mapping for both, so every
  consumer keeps reading `cells.get("a->b")`; a null cell is ABSENT (B3).
  Parsed files are cached per (path, mtime, size): one parse per process.

Served to the optimizer (T017) via `minutes(a, b)` and `travel_fit()`.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping

from BE.app.services.osrm_client import OsrmClient, OsrmTableError

ROW_SEP = "->"
DENSE_FORMAT = "dense-v1"


class DenseCells(Mapping):
    """Read-only `"a->b" -> {"km", "minutes"}` view over a dense matrix.

    `minutes[i][j]` None means OSRM could not route i->j: the key is absent
    (B3 infeasible), never a 0. Values are built on read; do not mutate.
    """

    def __init__(self, ids: list[str], minutes: list[list], km: list[list]):
        if len(minutes) != len(ids) or len(km) != len(ids):
            raise ValueError("dense matrix rows != len(ids)")
        self._index = {pid: i for i, pid in enumerate(ids)}
        self._minutes = minutes
        self._km = km
        self._len: int | None = None

    def _cell(self, key: str) -> dict | None:
        a, sep, b = key.partition(ROW_SEP)
        i, j = self._index.get(a), self._index.get(b)
        if not sep or i is None or j is None:
            return None
        minutes = self._minutes[i][j]
        if minutes is None:
            return None
        return {"km": self._km[i][j], "minutes": minutes}

    def __getitem__(self, key: str) -> dict:
        cell = self._cell(key)
        if cell is None:
            raise KeyError(key)
        return cell

    def get(self, key: str, default=None):
        cell = self._cell(key)
        return default if cell is None else cell

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self._cell(key) is not None

    def __iter__(self):
        ids = list(self._index)
        for i, a in enumerate(ids):
            row = self._minutes[i]
            for j, b in enumerate(ids):
                if row[j] is not None:
                    yield f"{a}{ROW_SEP}{b}"

    def __len__(self) -> int:
        if self._len is None:
            self._len = sum(1 for row in self._minutes
                            for minutes in row if minutes is not None)
        return self._len


def dense_document(ids: list[str], cells: Mapping, meta: dict) -> dict:
    """Legacy-shaped cells (`(a, b)` or `"a->b"` keys) -> dense-v1 document.

    Only homogeneous cells belong here: a per-cell `source` (haversine seed
    fill) cannot be represented and must stay in the legacy format.
    """
    def lookup(a: str, b: str):
        return cells.get((a, b)) or cells.get(f"{a}{ROW_SEP}{b}")

    minutes, km = [], []
    for a in ids:
        row_m, row_k = [], []
        for b in ids:
            cell = lookup(a, b)
            if cell is not None and cell.get("source", "osrm") != "osrm":
                raise ValueError(f"non-OSRM cell {a}->{b}: keep legacy format")
            row_m.append(None if cell is None else int(cell["minutes"]))
            row_k.append(None if cell is None else round(float(cell["km"]), 2))
        minutes.append(row_m)
        km.append(row_k)
    return {**meta, "format": DENSE_FORMAT, "ids": list(ids), "n": len(ids),
            "minutes": minutes, "km": km}


_DOC_CACHE: dict[str, tuple[tuple[int, int], dict]] = {}
_DOC_LOCK = threading.Lock()


def load_matrix_doc(path: str) -> dict:
    """Parsed matrix.json with `cells` as a Mapping (legacy dict or dense).

    Cached per (mtime, size), so a request does not re-parse the file. The
    returned document is SHARED: callers must treat it as read-only.
    """
    stat = os.stat(path)
    key = (stat.st_mtime_ns, stat.st_size)
    with _DOC_LOCK:
        hit = _DOC_CACHE.get(path)
    if hit is not None and hit[0] == key:
        return hit[1]
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("format") == DENSE_FORMAT:
        doc["cells"] = DenseCells(doc["ids"], doc.pop("minutes"), doc.pop("km"))
    elif doc.get("format") not in (None, ""):
        raise ValueError(f"unknown matrix format {doc.get('format')!r} in {path}")
    doc.setdefault("cells", {})
    with _DOC_LOCK:
        _DOC_CACHE[path] = (key, doc)
    return doc


def load_cells(snapshot_dir: str) -> Mapping:
    """`<snapshot_dir>/matrix.json` cells; {} when the snapshot has none."""
    try:
        return load_matrix_doc(os.path.join(snapshot_dir, "matrix.json"))["cells"]
    except (FileNotFoundError, NotADirectoryError):
        return {}


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
        data = load_matrix_doc(os.path.join(snapshot_dir, "matrix.json"))
        self.ids: list[str] = data["ids"]
        self.cells: Mapping = data["cells"]
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
