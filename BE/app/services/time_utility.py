"""u(t): how attractive a POI is at time t, by its `time_profile` (0..1, peak 1).

Shapes live in BE/data/priors/time_profiles.json (design prior, calibrated
from pilot logs later). Points are anchored to the sun (sunrise / sunset /
solar noon + offset) or to the clock, so a beach peaks right after sunrise in
June (~05:16) and in December (~06:09) alike. Opening hours are NOT here — the
solver reads hours.open; u(t) only ranks times inside them.

The objective uses ū = mean of u over the stay [start, start + dwell)
(TRAVELAGENT_CONTEXT §3), not u at the start minute.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
from functools import lru_cache

DAY = 1440
DANANG = (16.0544, 108.2022)          # lat, lon of the city centre
TZ_HOURS = 7                          # Asia/Ho_Chi_Minh, no DST
PRIORS = os.path.join(os.path.dirname(__file__), "..", "..", "data", "priors", "time_profiles.json")


def sun_times(day: dt.date, lat: float = DANANG[0], lon: float = DANANG[1],
              tz_hours: int = TZ_HOURS) -> dict[str, float]:
    """Sunrise, solar noon, sunset in local minutes after midnight (NOAA
    general solar position approximation, ~1-2 min accuracy; no network)."""
    n = day.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    la = math.radians(lat)
    cos_ha = (math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(decl))
              - math.tan(la) * math.tan(decl))
    ha = math.degrees(math.acos(max(-1.0, min(1.0, cos_ha))))
    noon = 720 - 4 * lon - eqtime + tz_hours * 60
    return {"sunrise": noon - 4 * ha, "solar_noon": noon, "sunset": noon + 4 * ha}


@lru_cache(maxsize=1)
def load_profiles(path: str = PRIORS) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["profiles"]


def _resolve(points: list[dict], sun: dict[str, float]) -> list[tuple[float, float]]:
    out = []
    for p in points:
        if p["ref"] == "clock":
            h, m = p["time"].split(":")
            t = int(h) * 60 + int(m)
        else:
            t = sun[p["ref"]] + p.get("offset_min", 0)
        out.append((t % DAY, float(p["u"])))
    return sorted(out)


def u_at(profile: str, minute: float, day: dt.date | None = None,
         lat: float = DANANG[0], lon: float = DANANG[1]) -> float:
    """u(t) for one minute of the day (piecewise linear, wraps midnight).
    Unknown profile -> 1.0 (neutral: never hides a POI)."""
    prof = load_profiles().get(profile)
    if not prof:
        return 1.0
    pts = _resolve(prof["points"], sun_times(day or dt.date.today(), lat, lon))
    t = minute % DAY
    if len(pts) == 1:
        return pts[0][1]
    for (t0, u0), (t1, u1) in zip(pts, pts[1:]):
        if t0 <= t <= t1:
            return u0 if t1 == t0 else u0 + (u1 - u0) * (t - t0) / (t1 - t0)
    # wrap segment: last point -> first point of the next day
    (t0, u0), (t1, u1) = pts[-1], (pts[0][0] + DAY, pts[0][1])
    tt = t if t >= t0 else t + DAY
    return u0 + (u1 - u0) * (tt - t0) / (t1 - t0)


def u_mean(profile: str, start_min: float, dwell_min: float, day: dt.date | None = None,
           lat: float = DANANG[0], lon: float = DANANG[1], step: int = 5) -> float:
    """ū: mean u over the stay [start, start + dwell) (objective term)."""
    if dwell_min <= 0:
        return u_at(profile, start_min, day, lat, lon)
    n = max(1, int(dwell_min // step))
    return sum(u_at(profile, start_min + i * dwell_min / n, day, lat, lon) for i in range(n)) / n
