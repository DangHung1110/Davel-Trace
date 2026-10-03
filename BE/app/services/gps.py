"""Mock GPS feed + demo timeline (T047, lane C).

CHOSEN LOCATION: BE/app/services/ (lane-c has no FE tree yet — FE/lib/
would orphan; move when the app lands, interface unchanged).
Timeline lives in data/gps/ (NOT data/snapshots — lane A owns that).

Interface (RealGpsFeed later implements the same methods — drop-in,
no caller change): GpsFeed.next() -> {at, lat, lon, trigger?} | None;
GpsFeed.triggers() lists replan trigger points for the dynamic-lite
demo. Timestamps must be monotonic (validated on load).
"""

from __future__ import annotations

import json


def load_timeline(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    points = data["points"] if isinstance(data, dict) else data
    for p in points:
        assert set(("at", "lat", "lon")) <= set(p), f"bad point {p}"
    ats = [p["at"] for p in points]
    assert ats == sorted(ats), "timeline must be monotonic"
    assert len(set(ats)) == len(ats), "duplicate timestamps"
    return points


class GpsFeed:
    """Mock feed replaying a timeline file in order."""

    def __init__(self, timeline: list[dict]):
        self._points = list(timeline)
        self._i = 0

    def next(self) -> dict | None:
        if self._i >= len(self._points):
            return None
        p = self._points[self._i]
        self._i += 1
        return {"at": p["at"], "lat": p["lat"], "lon": p["lon"],
                **({"trigger": p["trigger"]} if "trigger" in p else {})}

    def triggers(self) -> list[dict]:
        return [p for p in self._points if "trigger" in p]

    @property
    def done(self) -> bool:
        return self._i >= len(self._points)
