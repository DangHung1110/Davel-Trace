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


def _intervals(spec: str):
    """Yield (open, close) minutes for every 'HH:MM-HH:MM' in `spec`.

    A single hours element may pack several comma-separated intervals,
    e.g. "10:30-14:00, 16:30-22:30". Stray single-time fragments (no
    '-' or malformed) are skipped as closed so bad data cannot raise.
    """
    for part in (spec or "").split(","):
        part = part.strip()
        if part.count("-") != 1:
            continue  # stray/malformed time -> treat as closed
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


def parse_hours(hours: list) -> tuple[int, int] | None:
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


def status_map(checks: dict) -> dict:
    """Gate booleans -> 1/0 constraint_status map."""
    return {k: (1 if v else 0) for k, v in checks.items()}
