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


# B5 (FULL-AUDIT): money bands -> typical per-person spend. Thresholds mirror
# `BE/ml/data/price_from_raw.py` `band()` (cheap <100k, medium <=500k,
# expensive >500k); the midpoint is the "what a visitor actually pays" figure,
# matching the ingest rule that bands a menu by its midpoint, not its ceiling.
BAND_MIDPOINT = {"cheap": 100_000, "medium": 300_000, "expensive": 700_000}


def effective_fee(poi: dict | None) -> int | None:
    """Known spend for one POI in VND, or None when the price is unknown.

    Order:
    1. `ticket_vnd` — web-verified entry ticket, kept verbatim (0 = really free);
    2. `smart_tags.price_band` — cheap/medium/expensive -> BAND_MIDPOINT;
    3. a non-zero legacy `fee` — explicit data (fixtures, older snapshots);
    4. otherwise None = "giá chưa xác minh" (FR-024/FR-026 uncertainty).

    A missing/zero `fee` is UNKNOWN, never "miễn phí": the old `fee = 0`
    default made all 742 snapshot POIs look free, so the budget filter, the
    BCS gate and `total_cost` were all vacuous (FULL-AUDIT B5).
    """
    if not poi:
        return None
    ticket = poi.get("ticket_vnd")
    if ticket is not None:
        try:
            return int(ticket)
        except (TypeError, ValueError):
            return None
    band = (poi.get("smart_tags") or {}).get("price_band")
    if band in BAND_MIDPOINT:
        return BAND_MIDPOINT[band]
    try:
        fee = int(poi.get("fee") or 0)
    except (TypeError, ValueError):
        fee = 0
    return fee if fee > 0 else None


def total_fee(acts: list[dict], pois: dict) -> int:
    """Sum of KNOWN effective fees (unknown price adds 0, never assumed free)."""
    total = 0
    for a in acts:
        fee = effective_fee(pois.get(a.get("poi_id")))
        if fee is not None:
            total += fee
    return total


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


def load_matrix_cells(snapshot_dir: str) -> dict:
    """Read <snapshot_dir>/matrix.json -> cells dict."""
    return load_json(os.path.join(snapshot_dir, "matrix.json"))["cells"]
