"""Weather service + context wiring (T039+T040, lane C). Open-Meteo, cached.

fetch_forecast(lat, lon, transport, cache_path): hourly temp_c +
rain_prob -> {"fetched_at", "hourly": [{at, temp_c, rain_prob}],
"source": "open-meteo"|"cache", "stale": bool}. Offline/transport
error -> cache (labeled stale) or clear error when no cache.

apply_weather(): rain>70% trigger — weather-sensitive outdoor
activities in rainy hours swap to the best indoor alternative, with
explanation lines citing temp/rain (spec US6 acceptance).
Stdlib only; transport injectable for tests.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DANANG_LAT, DANANG_LON = 16.0544, 108.2022
RAIN_TRIGGER = 0.7
DEFAULT_CACHE = os.path.join(tempfile.gettempdir(), "travel_weather_cache.json")


def _urllib_transport(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def fetch_forecast(lat: float = DANANG_LAT, lon: float = DANANG_LON,
                   transport=None,
                   cache_path: str = DEFAULT_CACHE) -> dict:
    """Fetch hourly forecast; fall back to labeled cache offline."""
    transport = transport or _urllib_transport
    url = ("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,precipitation_probability",
        "timezone": "Asia/Bangkok"}))
    try:
        data = transport(url)
        hourly = [{"at": t, "temp_c": data["hourly"]["temperature_2m"][i],
                   "rain_prob": (data["hourly"]["precipitation_probability"][i]
                                 or 0) / 100.0}
                  for i, t in enumerate(data["hourly"]["time"])]
        snap = {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "hourly": hourly, "source": "open-meteo", "stale": False}
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(snap, f)
        return snap
    except Exception as e:  # noqa: BLE001 - offline path below
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                snap = json.load(f)
            snap["source"] = "cache"
            snap["stale"] = True
            snap["stale_reason"] = str(e)[:200]
            return snap
        raise RuntimeError(f"weather fetch failed, no cache: {e}")


def rain_at(forecast: dict, hour: str) -> float:
    """rain_prob for an "HH:MM" time (matches date+hour prefix, else nearest)."""
    hh = hour.split(":")[0]
    for h in forecast.get("hourly", []):
        if h["at"][11:13] == hh:
            return float(h["rain_prob"])
    return 0.0


def _indoor_score(p: dict) -> float:
    return float(p.get("rating") or 0.0) - (1.0 if p.get("weather_sensitive") else 0.0)


def apply_weather(activities: list[dict], by_id: dict,
                  forecast: dict) -> dict:
    """Rain>70% trigger: swap rainy outdoor acts to best indoor alt.

    Returns {"activities": [...], "swaps": [{from, to, reason}],
             "explanations": [...]}. Indoor = not weather_sensitive.
    """
    indoor = sorted((p for p in by_id.values() if not p.get("weather_sensitive")),
                    key=_indoor_score, reverse=True)
    acts, swaps, explanations = [], [], []
    used = {a["poi_id"] for a in activities}
    for a in activities:
        p = by_id.get(a["poi_id"], {})
        rain = rain_at(forecast, a["start"])
        if p.get("weather_sensitive") and rain > RAIN_TRIGGER:
            alt = next((c for c in indoor if c["poi_id"] not in used), None)
            if alt is not None:
                reason = (f"mua {round(rain * 100)}% luc {a['start']} nen doi "
                          f"{p.get('name', a['poi_id'])} -> {alt.get('name', alt['poi_id'])} (trong nha)")
                swaps.append({"from": a["poi_id"], "to": alt["poi_id"], "reason": reason})
                explanations.append(reason)
                used.add(alt["poi_id"])
                acts.append({**a, "poi_id": alt["poi_id"]})
                continue
            explanations.append(f"mua {round(rain * 100)}% luc {a['start']} nhung het cho trong nha")
        acts.append(a)
    return {"activities": acts, "swaps": swaps, "explanations": explanations}
