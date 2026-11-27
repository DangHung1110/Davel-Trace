"""Route matrix reader (T010, lane B). No haversine, a miss stays a miss.

TWO FILE FORMATS, ONE VIEW (Phase 3): the legacy `cells` dict
(`"a->b": {km, minutes[, source]}`) and the dense `dense-v1` format (`ids` +
`minutes`/`km` row-major lists, `null` = unroutable). 742 POIs are 550k pairs:
~47 MB as `cells`, ~5 MB dense. `load_matrix_doc` / `load_cells` return `cells`
as a read-only Mapping for both, so every consumer keeps reading
`cells.get("a->b")`; a null cell is ABSENT (B3: infeasible, never 0 or an
estimate, research R4). Parsed files are cached per (path, mtime, size).

The one estimate: a day that starts at a GPS fix (`gps_origin.py`) gets a row of its
own from `with_starts`, built from the rows of the places nearest to the fix plus the
short ride to them. Those cells say `source: gps_estimate`; every other cell is still
the matrix's own.
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

    @property
    def row_ids(self) -> list[str]:
        """poi_ids that own a row (cheap; avoids splitting every "a->b" key)."""
        return list(self._index)

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


GPS_ESTIMATE = "gps_estimate"


Anchor = tuple[str, float, float]  # (place with a row, ride minutes, ride km)


class StartCells(Mapping):
    """`cells` plus one row for each day start that is not a place (a GPS fix).

    `starts`: start id -> its anchors, (poi_id, ride minutes, ride km) each. A leg
    from a start is its best way through one anchor: the ride to it plus the anchor's
    own cell, rounded like the matrix (half up, a distinct pair is at least 1 minute);
    a place no anchor reaches stays absent (B3). Nothing leads TO a start: a day
    never ends there.
    """

    def __init__(self, base: Mapping, starts: dict[str, tuple[Anchor, ...]]):
        self.base = base
        self.starts = {sid: tuple(anchors) for sid, anchors in starts.items()}
        self._len: int | None = None

    @property
    def row_ids(self) -> list[str]:
        base_rows = getattr(self.base, "row_ids", None)
        if base_rows is None:
            base_rows = list(dict.fromkeys(key.split(ROW_SEP, 1)[0] for key in self.base))
        return list(base_rows) + list(self.starts)

    def _cell(self, key: str) -> dict | None:
        a, sep, b = key.partition(ROW_SEP)
        if not sep:
            return None
        anchors = self.starts.get(a)
        if anchors is None:
            return self.base.get(key)
        if b in self.starts:
            return None
        best: tuple[float, float] | None = None
        for anchor, access_min, access_km in anchors:
            if b == anchor:
                way = (access_min, access_km)
            else:
                cell = self.base.get(f"{anchor}{ROW_SEP}{b}")
                if cell is None:
                    continue
                way = (access_min + int(cell["minutes"]), access_km + float(cell["km"]))
            if best is None or way[0] < best[0]:
                best = way
        if best is None:
            return None
        return {"km": round(best[1], 2), "minutes": max(1, int(best[0] + 0.5)),
                "source": GPS_ESTIMATE}

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
        yield from self.base
        places = [pid for pid in self.row_ids if pid not in self.starts]
        for start in self.starts:
            for b in places:
                key = f"{start}{ROW_SEP}{b}"
                if self._cell(key) is not None:
                    yield key

    def __len__(self) -> int:
        # Counted once, without walking the base (a ~1M-cell matrix): `if cells`
        # (retrieval) must not cost a request a second.
        if self._len is None:
            places = [pid for pid in self.row_ids if pid not in self.starts]
            self._len = len(self.base) + sum(
                1 for start in self.starts for b in places
                if self._cell(f"{start}{ROW_SEP}{b}") is not None)
        return self._len

    def __bool__(self) -> bool:
        return bool(self.starts) or bool(self.base)

    def travel_minutes(self, ids: list[str]) -> dict[tuple[str, str], int]:
        """`travel_minutes` over `ids`: the places from the base, a start's legs here."""
        out = travel_minutes(self.base, [pid for pid in ids if pid not in self.starts])
        for a in ids:
            if a in self.starts:
                for b in ids:
                    cell = self._cell(f"{a}{ROW_SEP}{b}") if a != b else None
                    if cell is not None:
                        out[(a, b)] = int(cell["minutes"])
        return out


def with_starts(cells: Mapping, starts: dict[str, tuple[Anchor, ...]]) -> Mapping:
    """`cells` with a row for each GPS start (see StartCells); no start, `cells` as is."""
    return StartCells(cells, starts) if starts else cells


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
    if isinstance(cells, (DenseCells, StartCells)):
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


def has_row(cells: Mapping, pid: str) -> bool:
    """Does `pid` own a matrix row (can a day start there)?"""
    if isinstance(cells, DenseCells):
        return pid in cells._index
    if isinstance(cells, StartCells):
        return pid in cells.starts or has_row(cells.base, pid)
    prefix = f"{pid}{ROW_SEP}"
    return any(key.startswith(prefix) for key in cells)


def legs_from(cells: Mapping, origin: str, ids: list[str]) -> dict[tuple[str, str], int]:
    """{(origin, b): minutes} for every `b` of `ids` the origin's row reaches.

    The first drive of a day that starts at a base (a lodging, or the stop a replan
    resumes from), read off one row. A missing cell stays absent (B3), never 0.
    """
    legs: dict[tuple[str, str], int] = {}
    for b in ids:
        if b == origin:
            continue
        cell = cells.get(f"{origin}{ROW_SEP}{b}")
        if cell is not None:
            legs[(origin, b)] = int(cell["minutes"])
    return legs


def load_cells(snapshot_dir: str) -> Mapping:
    """`<snapshot_dir>/matrix.json` cells; {} when the snapshot has none."""
    try:
        return load_matrix_doc(os.path.join(snapshot_dir, "matrix.json"))["cells"]
    except (FileNotFoundError, NotADirectoryError):
        return {}


