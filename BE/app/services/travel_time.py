"""Time-of-day travel factor: travel(t) = matrix minutes x factor(zone_a, zone_b, t).

Priors live in BE/data/priors/travel_time_factors.json (design prior, no open
traffic source; calibrated from pilot logs). The OSRM matrix is free-flow.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

PRIORS = os.path.join(os.path.dirname(__file__), "..", "..", "data", "priors",
                      "travel_time_factors.json")


def _m(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


@lru_cache(maxsize=1)
def load(path: str = PRIORS) -> dict:
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    d["_bands"] = [(_m(b["from"]), _m(b["to"]), b["label"]) for b in d["bands"]]
    return d


def band_at(minute: float) -> str:
    t = int(minute) % 1440
    return next(lbl for lo, hi, lbl in load()["_bands"] if lo <= t < hi)


def factor(zone_a: str | None, zone_b: str | None, minute: float) -> float:
    """Unknown zone -> 1.0 (free flow). Two zones -> the larger factor."""
    f, b = load()["factors"], band_at(minute)
    vals = [f[z][b] for z in (zone_a, zone_b) if z in f]
    return max(vals) if vals else 1.0


def travel_at(base_min: float, zone_a: str | None, zone_b: str | None, depart_min: float) -> int:
    return int(round(base_min * factor(zone_a, zone_b, depart_min)))
