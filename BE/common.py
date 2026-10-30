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


DAY_MIN = 24 * 60


def day_spans(spec: str) -> list[tuple[int, int]]:
    """Sorted, merged open spans of one hours element on a same-day clock.

    A span that closes at or before it opens runs past midnight, so its close
    moves to the next day ("19:30-03:00" -> 1170..1620, "09:00-00:00" ->
    540..1440). A day trip never uses the early-morning tail of the previous
    evening, so that tail is not modelled here (`in_range` still accepts it).
    """
    spans = sorted((o, c if c > o else c + DAY_MIN) for o, c in _intervals(spec))
    merged: list[tuple[int, int]] = []
    for o, c in spans:
        if merged and o <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], c))
        else:
            merged.append((o, c))
    return merged


def open_windows(hours: list | None) -> list[tuple[int, int]] | None:
    """Same-day open windows that every listed variant agrees on.

    Each `opening_hours` element is one variant of the week: the crawl keeps
    the distinct weekday ranges, e.g. ["10:30-14:00, 17:30-20:45",
    "17:30-20:45"] = lunch closed on some days. The trip weekday is not
    matched to them, so the safe answer is the intersection (open on every
    variant). None = no parsable hours (caller picks the default); [] = the
    variants share no open time.
    """
    variants = [s for s in (day_spans(h) for h in hours or []) if s]
    if not variants:
        return None
    common = variants[0]
    for spans in variants[1:]:
        common = [(max(a, c), min(b, d)) for a, b in common for c, d in spans
                  if max(a, c) < min(b, d)]
    return sorted(common)


# Hours assumed for a POI that has none, so a missing value never reads as
# "open all trip" (a pagoda at 23:05). Each entry is the 15-minute slots in
# which >= SAFE_HOURS_SHARE of that group's POIs with sourced hours are open,
# measured on danang-v1 by `BE/ml/data/normalize_fields.py --safe-hours`
# (test_normalize_fields fails when the table drifts from the snapshot).
# Sightseeing categories are pooled (too few rows each). [] = no such time
# (markets mix dawn wet markets with night markets): not schedulable until
# real hours land. Other groups (lodging, transport) keep the trip window.
SAFE_HOURS_SHARE = 0.9
SIGHTSEEING_CATS = ("attraction", "beach", "landmark", "museum", "nature", "park",
                    "viewpoint")
SAFE_HOURS: dict[str, list[str]] = {
    "bar": ["19:30-23:45"],
    "cafe": ["07:30-19:30"],
    "market": [],
    "restaurant": ["17:00-21:00"],
    "sightseeing": ["09:00-17:00"],
    "spa": ["09:30-19:30"],
}


def hours_group(cat: str) -> str:
    """SAFE_HOURS key of a category ("" when it has no assumed hours)."""
    if cat in SIGHTSEEING_CATS:
        return "sightseeing"
    return cat if cat in ("restaurant", "cafe", "bar", "spa", "market") else ""


def poi_open_windows(poi: dict) -> list[tuple[int, int]] | None:
    """`open_windows` of the POI's hours, else of its group's SAFE_HOURS.

    None = neither (the caller keeps its default, e.g. the trip window for a
    legacy fixture without `cat`); [] = no time is safe to schedule.
    """
    wins = open_windows(poi.get("opening_hours"))
    if wins is not None:
        return wins
    safe = SAFE_HOURS.get(hours_group(poi.get("cat") or ""))
    if safe is None:
        return None
    return open_windows(safe) or []


def parse_hours(hours: list | None) -> tuple[int, int] | None:
    """First window of `open_windows` as minutes, or None when unset.

    Variants that share no open time give (0, 0): nothing fits, rather than
    the caller's "open all trip" default.
    """
    windows = open_windows(hours)
    if windows is None:
        return None
    return windows[0] if windows else (0, 0)


# Price level assumed for a POI with no price evidence (`price_level` null):
# the middle band, which is what the crawl placeholder 2 used to say
# silently. Ranking is unchanged; retrieval labels the price as unverified.
UNKNOWN_PRICE_LEVEL = 2


def price_level_of(poi: dict) -> int:
    """POI price level 1..3, UNKNOWN_PRICE_LEVEL when null or absent."""
    level = poi.get("price_level")
    return UNKNOWN_PRICE_LEVEL if level is None else int(level)


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
