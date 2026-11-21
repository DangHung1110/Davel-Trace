"""Climate prior per zone x month x hour from 10 years of hourly reanalysis.

    python BE/tools/build_climate.py              # fetch (cached) + write BE/data/priors/climate.json

Source: Open-Meteo historical weather API (ERA5 / ERA5-Land reanalysis,
CC BY 4.0), 2016-01-01..2025-12-31, one point per zone (the zone's POI
centroid). Only coordinates are sent. Raw responses are cached in
%TEMP%/davel_climate (not committed); the aggregate is committed.

Per zone, month (1-12) and local hour (0-23):
  temp_c        mean air temperature
  feels_c       mean apparent temperature;  feels_p90 its 90th percentile
  rain_prob     share of hours with precipitation >= 0.5 mm
  rain_mm       mean precipitation (mm/h)
  humidity      mean relative humidity (%)
  wind_kmh      mean wind speed at 10 m
Per zone and month: rainy_day_prob = share of days with >= 5 mm.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics as st
import sys
import tempfile
import urllib.parse
import urllib.request
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SNAP = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2", "pois.json")
OUT = os.path.join(ROOT, "BE", "data", "priors", "climate.json")
CACHE = os.path.join(tempfile.gettempdir(), "davel_climate")
URL = "https://archive-api.open-meteo.com/v1/archive"
START, END = "2016-01-01", "2025-12-31"
VARS = "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m,wind_speed_10m"
RAIN_HOUR_MM, RAIN_DAY_MM = 0.5, 5.0


def zone_points() -> dict[str, tuple[float, float]]:
    with open(SNAP, encoding="utf-8") as f:
        pois = [p for p in json.load(f)["pois"] if p["status"] == "active"]
    acc = defaultdict(list)
    for p in pois:
        acc[p["zone"]].append((p["lat"], p["lon"]))
    return {z: (round(st.mean(a for a, _ in v), 4), round(st.mean(b for _, b in v), 4))
            for z, v in sorted(acc.items())}


def fetch(lat: float, lon: float) -> dict:
    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "start_date": START,
                                "end_date": END, "hourly": VARS, "timezone": "Asia/Bangkok"})
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha1(q.encode()).hexdigest() + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with urllib.request.urlopen(f"{URL}?{q}", timeout=120) as r:
        data = json.load(r)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def aggregate(data: dict) -> dict:
    h = data["hourly"]
    cell = defaultdict(lambda: defaultdict(list))
    day_mm = defaultdict(float)
    for i, t in enumerate(h["time"]):
        if h["temperature_2m"][i] is None:
            continue
        month, hour = int(t[5:7]), int(t[11:13])
        c = cell[(month, hour)]
        mm = h["precipitation"][i] or 0.0
        c["t"].append(h["temperature_2m"][i])
        c["f"].append(h["apparent_temperature"][i])
        c["mm"].append(mm)
        c["rh"].append(h["relative_humidity_2m"][i])
        c["w"].append(h["wind_speed_10m"][i])
        day_mm[t[:10]] += mm
    months = {}
    for m in range(1, 13):
        hours = []
        for hr in range(24):
            c = cell[(m, hr)]
            f = sorted(c["f"])
            hours.append({"hour": hr, "temp_c": round(st.mean(c["t"]), 1),
                          "feels_c": round(st.mean(f), 1),
                          "feels_p90": round(f[int(0.9 * (len(f) - 1))], 1),
                          "rain_prob": round(sum(x >= RAIN_HOUR_MM for x in c["mm"]) / len(c["mm"]), 3),
                          "rain_mm": round(st.mean(c["mm"]), 2),
                          "humidity": round(st.mean(c["rh"])),
                          "wind_kmh": round(st.mean(c["w"]), 1)})
        days = [v for d, v in day_mm.items() if int(d[5:7]) == m]
        months[str(m)] = {"rainy_day_prob": round(sum(v >= RAIN_DAY_MM for v in days) / len(days), 3),
                          "hours": hours}
    return months


def main() -> int:
    zones = {}
    for z, (lat, lon) in zone_points().items():
        data = fetch(lat, lon)
        zones[z] = {"lat": lat, "lon": lon, "elevation_m": data.get("elevation"),
                    "months": aggregate(data)}
        m6, m11 = zones[z]["months"]["6"], zones[z]["months"]["11"]
        print(z, lat, lon, "elev", data.get("elevation"),
              "| Jun 13h feels", m6["hours"][13]["feels_c"], "rainy days", m6["rainy_day_prob"],
              "| Nov 13h feels", m11["hours"][13]["feels_c"], "rainy days", m11["rainy_day_prob"])
    out = {"version": "climate_v1", "created": "2026-11-20",
           "source": "Open-Meteo historical weather API (ERA5/ERA5-Land reanalysis), CC BY 4.0",
           "period": f"{START}..{END}", "timezone": "Asia/Ho_Chi_Minh (UTC+7)",
           "status": "measured climatology (reanalysis), not a forecast; a live forecast wins when the trip is within its range",
           "rain_hour_mm": RAIN_HOUR_MM, "rain_day_mm": RAIN_DAY_MM, "zones": zones}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print("wrote", OUT, os.path.getsize(OUT), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
