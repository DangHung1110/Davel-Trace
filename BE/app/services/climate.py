"""Climate prior (zone x month x hour) from BE/data/priors/climate.json.

Measured climatology (10 years of ERA5 reanalysis via Open-Meteo, built by
BE/tools/build_climate.py). It is the fallback when a trip is beyond the live
forecast's range; `as_forecast` returns the same shape as
`weather.fetch_forecast`, so trip_ctx can read it unchanged.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from functools import lru_cache

PRIORS = os.path.join(os.path.dirname(__file__), "..", "..", "data", "priors", "climate.json")
DEFAULT_ZONE = "trung_tam"


@lru_cache(maxsize=1)
def load(path: str = PRIORS) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def climate_at(zone: str | None, month: int, minute: float) -> dict:
    """Hourly climate cell: temp_c, feels_c, feels_p90, rain_prob, rain_mm, humidity, wind_kmh."""
    zones = load()["zones"]
    z = zones.get(zone) or zones[DEFAULT_ZONE]
    return z["months"][str(int(month))]["hours"][int(minute) // 60 % 24]


def rainy_day_prob(zone: str | None, month: int) -> float:
    zones = load()["zones"]
    return (zones.get(zone) or zones[DEFAULT_ZONE])["months"][str(int(month))]["rainy_day_prob"]


def as_forecast(day: dt.date, zone: str | None = None) -> dict:
    """weather.fetch_forecast-shaped dict for `day` built from the climate prior."""
    hourly = []
    for hr in range(24):
        c = climate_at(zone, day.month, hr * 60)
        hourly.append({"at": f"{day.isoformat()}T{hr:02d}:00", "temp_c": c["temp_c"],
                       "rain_prob": c["rain_prob"]})
    return {"fetched_at": None, "hourly": hourly, "source": "climate_prior", "stale": False}
