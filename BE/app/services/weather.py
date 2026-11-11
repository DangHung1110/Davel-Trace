"""Weather service (T039, lane C). Open-Meteo, cached.

fetch_forecast(lat, lon, transport, cache_path): hourly temp_c +
rain_prob -> {"fetched_at", "hourly": [{at, temp_c, rain_prob}],
"source": "open-meteo"|"cache", "stale": bool}. Offline/transport
error -> cache (labeled stale) or clear error when no cache.
Stdlib only; transport injectable for tests.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.parse

from BE.app.services import fetch_json

DANANG_LAT, DANANG_LON = 16.0544, 108.2022
DEFAULT_CACHE = os.path.join(tempfile.gettempdir(), "travel_weather_cache.json")

# Every plan request used to call Open-Meteo (3 s timeout, ~0.3-1 s online, the
# full timeout offline). An hourly forecast does not change inside a quarter of
# an hour, so a fresh fetch is kept in memory for FORECAST_TTL_S and a failed one
# for FAILURE_TTL_S (an offline box then answers from the file cache at once
# instead of waiting for the timeout on every plan). Keyed by the transport too,
# so an injected test transport never sees another one's answer.
FORECAST_TTL_S = 15 * 60
FAILURE_TTL_S = 60
_MEMO: dict[tuple, tuple[float, dict | None]] = {}
_MEMO_LOCK = threading.Lock()


def clear_memo() -> None:
    with _MEMO_LOCK:
        _MEMO.clear()


def _memo_get(key: tuple) -> tuple[bool, dict | None]:
    """(hit, forecast) when the memo holds a fresh entry (None = a fresh failure)."""
    with _MEMO_LOCK:
        hit = _MEMO.get(key)
    if hit is None:
        return False, None
    at, snap = hit
    ttl = FORECAST_TTL_S if snap is not None else FAILURE_TTL_S
    if time.monotonic() - at > ttl:
        return False, None
    return True, snap


def _urllib_transport(url: str) -> dict:
    return fetch_json(url, timeout=20)


def fetch_forecast(lat: float = DANANG_LAT, lon: float = DANANG_LON,
                   transport=None,
                   cache_path: str = DEFAULT_CACHE) -> dict:
    """Fetch hourly forecast; fall back to labeled cache offline."""
    transport = transport or _urllib_transport
    key = (float(lat), float(lon), cache_path, transport)
    hit, memo = _memo_get(key)
    if hit and memo is not None:
        return dict(memo)
    url = ("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,precipitation_probability",
        "timezone": "Asia/Bangkok"}))
    try:
        if hit:  # a fetch failed moments ago: do not wait on it again yet
            raise RuntimeError("weather fetch failed recently, not retried yet")
        data = transport(url)
        hourly = [{"at": t, "temp_c": data["hourly"]["temperature_2m"][i],
                   "rain_prob": (data["hourly"]["precipitation_probability"][i]
                                 or 0) / 100.0}
                  for i, t in enumerate(data["hourly"]["time"])]
        snap = {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "hourly": hourly, "source": "open-meteo", "stale": False}
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(snap, f)
        with _MEMO_LOCK:
            _MEMO[key] = (time.monotonic(), snap)
        return dict(snap)
    except Exception as e:  # noqa: BLE001 - offline path below
        if not hit:
            with _MEMO_LOCK:
                _MEMO[key] = (time.monotonic(), None)
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                snap = json.load(f)
            snap["source"] = "cache"
            snap["stale"] = True
            snap["stale_reason"] = str(e)[:200]
            return snap
        raise RuntimeError(f"weather fetch failed, no cache: {e}")


