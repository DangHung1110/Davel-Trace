"""Services package (T001, lane C). Domain services land per-lane:
lane C (llm, parser, retrieval, ...), lane B (matrix, gate, optimizer,
...), lane A (snapshot). No stubs here — each lane adds its own files."""

from __future__ import annotations

import json
import urllib.request


def to_min(t: str) -> int:
    """'HH:MM' -> minutes since midnight. Shared by rank/retrieval/itinerary."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def fetch_json(url: str, data: bytes | None = None, headers: dict | None = None,
               timeout: int = 20) -> dict:
    """urllib request -> parsed JSON. Shared by llm/weather transports."""
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)
