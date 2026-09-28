"""Shared stdlib glue for BE scripts (one spot for copy-pasted helpers).

Deliberately tiny and dependency-free: time <-> minutes conversion and
snapshot JSON reads that were duplicated across `eval/` and `ml/`.
No config, no classes, no third-party imports (DoD).

ponytail: only genuinely repeated glue lives here. Domain schemas stay in
`app/schemas/` and validated snapshot loading stays in
`app/services/snapshot.py` (that one is intentionally stricter, stdlib-only
so it does not depend on lane C Pydantic).
"""

from __future__ import annotations

import json
import os
from typing import Any


def to_min(hhmm: str) -> int:
    """'HH:MM' -> minutes since midnight (well-formed input assumed)."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def hhmm(minutes: int) -> str:
    """Minutes since midnight -> 'HH:MM'."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_pois(snapshot_dir: str, by_id: bool = False):
    """Read <snapshot_dir>/pois.json -> list of POIs, or {poi_id: POI}."""
    pois = load_json(os.path.join(snapshot_dir, "pois.json"))["pois"]
    return {p["poi_id"]: p for p in pois} if by_id else pois


def load_matrix_cells(snapshot_dir: str) -> dict:
    """Read <snapshot_dir>/matrix.json -> cells dict."""
    return load_json(os.path.join(snapshot_dir, "matrix.json"))["cells"]
