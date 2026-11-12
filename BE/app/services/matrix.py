"""Route matrix reader (T010, lane B). No haversine, a miss stays a miss.

TWO FILE FORMATS, ONE VIEW (Phase 3): the legacy `cells` dict
(`"a->b": {km, minutes[, source]}`) and the dense `dense-v1` format (`ids` +
`minutes`/`km` row-major lists, `null` = unroutable). 742 POIs are 550k pairs:
~47 MB as `cells`, ~5 MB dense. `load_matrix_doc` / `load_cells` return `cells`
as a read-only Mapping for both, so every consumer keeps reading
`cells.get("a->b")`; a null cell is ABSENT (B3: infeasible, never 0 or an
estimate, research R4). Parsed files are cached per (path, mtime, size).
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping

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

    def travel_minutes(self, ids: list[str]) -> dict[tuple[str, str], int]:
        """{(a, b): minutes} over `ids`, read straight off the rows.

        The same cells `get("a->b")` returns, without building a key string
        per pair (a profile reads ~13k pairs a request). An unknown id or an
        unroutable pair stays absent (B3), never 0.
        """
        known = [(pid, self._index[pid]) for pid in ids if pid in self._index]
        out: dict[tuple[str, str], int] = {}
        for a, i in known:
            row = self._minutes[i]
            for b, j in known:
                if i != j and row[j] is not None:
                    out[(a, b)] = int(row[j])
        return out


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


def travel_minutes(cells: Mapping, ids: list[str]) -> dict[tuple[str, str], int]:
    """{(a, b): minutes} for every routable ordered pair of `ids`.

    Dense cells answer from their rows; legacy dict cells are read key by key.
    A missing cell stays ABSENT (B3: infeasible, never an estimate).
    """
    if isinstance(cells, DenseCells):
        return cells.travel_minutes(ids)
    travel: dict[tuple[str, str], int] = {}
    for a in ids:
        for b in ids:
            if a == b:
                continue
            cell = cells.get(f"{a}{ROW_SEP}{b}")
            if cell is not None:
                travel[(a, b)] = int(cell["minutes"])
    return travel


def load_cells(snapshot_dir: str) -> Mapping:
    """`<snapshot_dir>/matrix.json` cells; {} when the snapshot has none."""
    try:
        return load_matrix_doc(os.path.join(snapshot_dir, "matrix.json"))["cells"]
    except (FileNotFoundError, NotADirectoryError):
        return {}


