"""POI retrieval/filter (T015, lane C). Hard-constraint filter + candidates.

Reads pois.json directly with json stdlib (STUB-NOTE: lane-A snapshot
loader T008 wires in at phase-PR — same schema, swap one line).
Unverified handling (FR-013) and uncertainty labels are T024 (US2);
here unverified POIs are excluded unless must-visit (flagged).

Rules:
- avoid -> always excluded (reason).
- must_visit -> always kept (violations flagged in reasons, validator
  decides later per FR-031).
- type: trip.activities keywords map to POI types (empty = no filter).
- budget: fee > budget -> excluded.
- hours: no overlap with trip window -> excluded (unless must-visit).
"""

from __future__ import annotations

import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

ACTIVITY_TYPE_MAP = {
    "biển": ["beach"], "tắm": ["beach"], "núi": ["nature"], "leo": ["nature"],
    "ăn": ["restaurant"], "mì": ["restaurant"], "quán": ["restaurant", "market"],
    "văn hóa": ["museum"], "bảo tàng": ["museum"], "lịch sử": ["museum"],
    "chợ": ["market"], "mua sắm": ["market"], "check-in": ["landmark"],
    "cầu": ["landmark"],
}


def load_pois_json(path: str) -> list[dict]:
    """STUB-NOTE: replaced by lane-A snapshot loader (T008) at phase-PR."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["pois"] if isinstance(data, dict) else data


def _to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _overlaps(hours: list[str], ws: int, we: int) -> bool:
    for h in hours or []:
        o, c = h.split("-")
        o, c = _to_min(o), _to_min(c)
        if o <= c and o < we and ws < c:
            return True
        if o > c and (ws < c or o < we):
            return True
    return not hours


def wanted_types(activities: list[str]) -> set[str]:
    out: set[str] = set()
    for a in activities or []:
        low = a.lower()
        for kw, types in ACTIVITY_TYPE_MAP.items():
            if kw in low:
                out.update(types)
    return out


def retrieve(trip: dict, pois: list[dict]) -> dict:
    """Return {"candidates": [{poi_id, reasons[]}], "excluded": [{poi_id, reason}]}."""
    ws, we = _to_min(trip.get("start_time", "07:00")), _to_min(trip.get("end_time", "18:00"))
    budget = int(trip.get("budget", 0))
    must = set(trip.get("must_visit", []))
    avoid = set(trip.get("avoid", []))
    types = wanted_types(trip.get("activities", []))
    candidates, excluded = [], []
    for p in pois:
        pid = p.get("poi_id")
        if pid in avoid:
            excluded.append({"poi_id": pid, "reason": "avoid"})
            continue
        reasons: list[str] = []
        if pid in must:
            if not p.get("verified"):
                reasons.append("must-visit (chua xac minh)")
            if not _overlaps(p.get("opening_hours", []), ws, we):
                reasons.append("must-visit (ngoai gio mo cua)")
            reasons.append("must-visit")
            candidates.append({"poi_id": pid, "reasons": reasons})
            continue
        if not p.get("verified"):
            excluded.append({"poi_id": pid, "reason": "chua xac minh (FR-013)"})
            continue
        if types and p.get("type") not in types:
            excluded.append({"poi_id": pid, "reason": "khong khop loai hoat dong"})
            continue
        if int(p.get("fee", 0)) > budget:
            excluded.append({"poi_id": pid, "reason": "vuot ngan sach"})
            continue
        if not _overlaps(p.get("opening_hours", []), ws, we):
            excluded.append({"poi_id": pid, "reason": "dong cua trong khung gio"})
            continue
        reasons.append(f"khop loai {p.get('type')}")
        candidates.append({"poi_id": pid, "reasons": reasons})
    return {"candidates": candidates, "excluded": excluded}
