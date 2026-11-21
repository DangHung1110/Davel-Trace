"""Services package (T001, lane C)."""

from __future__ import annotations

import json
import urllib.request


def fetch_json(url: str, data: bytes | None = None, headers: dict | None = None,
               timeout: int = 20) -> dict:
    """urllib request -> parsed JSON. Shared by llm/weather transports."""
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)
