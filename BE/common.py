"""Shared stdlib glue for BE (one spot for copy-pasted helpers).

T061c survivor: time <-> minutes, opening-hours parsing, plan fee/deadline
and JSON/snapshot reads that were duplicated across `eval/`, `ml/` and the
app services. `BE.app.services.common` re-exports these names, so lane B/C
callers keep their imports while a single implementation lives here.
No config, no classes, no third-party imports (DoD).

ponytail: only genuinely repeated glue lives here. Domain schemas stay in
`app/schemas/` and validated snapshot loading stays in
`app/services/snapshot.py` (intentionally stricter, stdlib-only).
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


# T061c: the survivor helpers below were copy-pasted across app services /
# eval. They live here once; `BE.app.services.common` re-exports them.
hh = hhmm  # lane-B alias (BE.app.services.common.hh)


def _intervals(spec: str):
    """Yield (open, close) minutes for every 'HH:MM-HH:MM' in `spec`.

    One element may pack several comma-separated intervals, e.g.
    "10:30-14:00, 16:30-22:30". Stray/malformed fragments are skipped as
    closed so bad data cannot raise.
    """
    for part in (spec or "").split(","):
        part = part.strip()
        if part.count("-") != 1:
            continue
        o, c = part.split("-")
        yield to_min(o), to_min(c)


def in_range(start: int, end: int, spec: str) -> bool:
    """True iff [start, end] fits any 'HH:MM-HH:MM' window (wraps midnight)."""
    for o, c in _intervals(spec):
        if o <= c:
            if o <= start and end <= c:
                return True
        elif start >= o or end <= c:
            return True
    return False


def parse_hours(hours: list | None) -> tuple[int, int] | None:
    """First 'HH:MM-HH:MM' opening span as minutes, or None when unset."""
    if not hours:
        return None
    for spec in hours:
        for o, c in _intervals(spec):
            return o, c
    return None


def total_fee(acts: list[dict], pois: dict) -> int:
    """Sum of POI fees for the activities (unknown POI/fee -> 0)."""
    return sum(int((pois.get(a.get("poi_id"), {}) or {}).get("fee", 0))
               for a in acts)


def plan_cost(itinerary: dict, pois: dict) -> int:
    """Itinerary cost: explicit `total_cost` wins, else the POI fee sum."""
    if "total_cost" in itinerary:
        return int(itinerary["total_cost"])
    return total_fee(itinerary.get("activities", []), pois)


def deadline(trip: dict, default: str = "18:00") -> int:
    """ETB hard within-day deadline: min(end_time, return_time) minutes."""
    end = to_min(trip.get("end_time", default))
    rt = trip.get("return_time")
    return min(end, to_min(rt)) if rt else end


def status_map(checks: dict) -> dict:
    """Gate booleans -> 1/0 constraint_status map."""
    return {k: (1 if v else 0) for k, v in checks.items()}


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_pois(snapshot_dir: str, by_id: bool = False):
    """Read <snapshot_dir>/pois.json -> list of POIs, or {poi_id: POI}."""
    pois = load_json(os.path.join(snapshot_dir, "pois.json"))["pois"]
    return {p["poi_id"]: p for p in pois} if by_id else pois


def load_matrix_cells(snapshot_dir: str):
    """<snapshot_dir>/matrix.json -> cells Mapping (legacy dict or dense-v1).

    Raises FileNotFoundError like before when the snapshot has no matrix.
    """
    from BE.app.services.matrix import load_matrix_doc
    return load_matrix_doc(os.path.join(snapshot_dir, "matrix.json"))["cells"]
