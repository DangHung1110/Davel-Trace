"""Shared lane-B service helpers (ponytail: merged per-file copies).

gate/validator/response/profiles/replan each carried private copies of
the same time parsing, opening-hours containment, fee total and
constraint-status map. One implementation lives here now.

ponytail: modules are imported as `BE.app.services.*` (tests insert the
repo root, `server.py` runs from it), so the per-module `_REPO_ROOT`
sys.path bootstrap was redundant and has been dropped.
"""

from __future__ import annotations


def to_min(t: str) -> int:
    """'HH:MM' -> minutes since midnight."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def hh(m: int) -> str:
    """Minutes since midnight -> 'HH:MM'."""
    return f"{m // 60:02d}:{m % 60:02d}"


def in_range(start: int, end: int, spec: str) -> bool:
    """True iff [start, end] fits an 'HH:MM-HH:MM' window (wraps midnight)."""
    o, c = spec.split("-")
    o, c = to_min(o), to_min(c)
    if o <= c:
        return o <= start and end <= c
    return start >= o or end <= c


def parse_hours(hours: list) -> tuple[int, int] | None:
    """First 'HH:MM-HH:MM' opening span as minutes, or None when unset."""
    if not hours:
        return None
    o, c = hours[0].split("-")
    return to_min(o), to_min(c)


def total_fee(acts: list[dict], pois: dict) -> int:
    """Sum of POI fees for the activities (unknown POI/fee -> 0)."""
    return sum(int((pois.get(a.get("poi_id"), {}) or {}).get("fee", 0))
               for a in acts)


def status_map(checks: dict) -> dict:
    """Gate booleans -> 1/0 constraint_status map."""
    return {k: (1 if v else 0) for k, v in checks.items()}
