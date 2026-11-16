"""Mobility prior runtime (T062 M1, lane A). P(next|prev, time-bucket).

Backoff: missing (prev, bucket) -> unigram -> uniform floor (never 0).
logprob() in nats, symmetric-safe for feature use (directional by design).
"""

from __future__ import annotations

import json
import math
import os

_prior = None


def _path() -> str:
    return os.path.join(os.path.dirname(__file__), "transition_prior.json")


def load(path: str = ""):
    global _prior
    if _prior is None:
        with open(path or _path(), encoding="utf-8") as f:
            _prior = json.load(f)
    return _prior


def bucket_of_hour(hour: int) -> str:
    if 5 <= hour < 11:
        return "sang"
    if 11 <= hour < 14:
        return "trua"
    if 14 <= hour < 18:
        return "chieu"
    return "toi"


def prob(next_cat: str, prev_cat: str, hour: int = 9) -> float:
    p = load()
    cats = p["cats"]
    b = bucket_of_hour(hour)
    v = p["trans"].get(b, {}).get(prev_cat, {}).get(next_cat)
    if v is not None:
        return v
    u = p["unigram"].get(next_cat)
    if u:
        return u
    return 1.0 / len(cats)


def logprob(next_cat: str, prev_cat: str, hour: int = 9) -> float:
    return math.log(prob(next_cat, prev_cat, hour))
