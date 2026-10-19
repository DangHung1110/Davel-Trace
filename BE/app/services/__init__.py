"""Services package (T001, lane C). Domain services land per-lane:
lane C (llm, parser, retrieval, ...), lane B (matrix, gate, optimizer,
...), lane A (snapshot). No stubs here — each lane adds its own files."""

from __future__ import annotations

import json
import urllib.request

# T061c: single implementation in BE/common.py; re-exported here so
# rank/retrieval import sites stay unchanged.
from BE.common import to_min  # noqa: F401


def fetch_json(url: str, data: bytes | None = None, headers: dict | None = None,
               timeout: int = 20) -> dict:
    """urllib request -> parsed JSON. Shared by llm/weather transports."""
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)
