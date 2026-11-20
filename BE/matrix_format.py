"""matrix.json on-disk formats (stdlib only).

Two formats, one read API (`cells_of(doc)` -> mapping "a->b" -> {"km", "minutes"}):

- legacy (v1): ``"cells": {"a->b": {"km": .., "minutes": .., ["source"]}}``.
  About 75 bytes per cell, because every key repeats two poi_ids: the
  988-POI danang-v2 matrix was 73.6 MB.
- dense (``"format": "dense_v1"``): ``ids`` + row-major flat lists
  ``minutes`` (int, -1 = unroutable/missing, never a silent 0) and ``km``
  (1 decimal), cell (i, j) at ``i * n + j``. Same data, ~8 MB, and far less
  memory once loaded (two int/float lists instead of ~1M dicts).

`DenseCells` is a read-only Mapping with the legacy key shape, so callers that
do ``cells.get(f"{a}->{b}")`` or iterate keys work unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping

SEP = "->"
DENSE = "dense_v1"


class DenseCells(Mapping):
    def __init__(self, ids: list[str], minutes: list[int], km: list[float]):
        n = len(ids)
        if len(minutes) != n * n or len(km) != n * n:
            raise ValueError(f"dense matrix: {len(minutes)} cells for n={n}")
        self.ids, self.n = list(ids), n
        self._idx = {pid: i for i, pid in enumerate(self.ids)}
        self._min, self._km = minutes, km

    @property
    def row_ids(self) -> list[str]:
        """poi_ids that own a row (cheap; avoids splitting ~1M keys)."""
        return self.ids

    def _pos(self, key: str) -> int | None:
        a, _, b = key.partition(SEP)
        i, j = self._idx.get(a), self._idx.get(b)
        if i is None or j is None:
            return None
        k = i * self.n + j
        return k if self._min[k] >= 0 else None

    def __getitem__(self, key: str) -> dict:
        k = self._pos(key)
        if k is None:
            raise KeyError(key)
        return {"km": self._km[k], "minutes": self._min[k]}

    def __contains__(self, key) -> bool:
        return isinstance(key, str) and self._pos(key) is not None

    def __iter__(self):
        for i, a in enumerate(self.ids):
            base = i * self.n
            for j, b in enumerate(self.ids):
                if self._min[base + j] >= 0:
                    yield f"{a}{SEP}{b}"

    def __len__(self) -> int:
        return sum(1 for m in self._min if m >= 0)


def cells_of(doc: dict) -> Mapping:
    """The cell mapping of a matrix document, whichever format it is in."""
    if doc.get("format") == DENSE:
        return DenseCells(doc["ids"], doc["minutes"], doc["km"])
    return doc.get("cells", {})


def to_dense(doc: dict) -> dict:
    """Legacy document -> dense document (metadata kept, `cells` replaced).
    Refuses mixed per-cell sources: dense keeps one document-level `source`."""
    if doc.get("format") == DENSE:
        return doc
    ids, cells = doc["ids"], doc["cells"]
    srcs = {c.get("source", doc.get("source")) for c in cells.values()}
    if len(srcs) > 1:
        raise ValueError(f"dense format needs one cell source, found {sorted(map(str, srcs))}")
    minutes, km = [], []
    for a in ids:
        for b in ids:
            c = cells.get(f"{a}{SEP}{b}")
            minutes.append(-1 if c is None else int(c["minutes"]))
            km.append(-1.0 if c is None else round(float(c.get("km", 0.0)), 1))
    out = {k: v for k, v in doc.items() if k != "cells"}
    out.update({"format": DENSE, "minutes": minutes, "km": km})
    return out


def main(argv=None) -> int:
    """python -m BE.matrix_format <matrix.json>   # rewrite in place as dense_v1"""
    import json
    import sys
    path = (argv or sys.argv[1:])[0]
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    dense = to_dense(doc)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dense, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(path, "->", DENSE, "n =", len(dense["ids"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
