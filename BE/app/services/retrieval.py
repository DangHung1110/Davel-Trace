"""POI retrieval/filter (T015 + T024, lane C). Hard filter + uncertainty.

Reads pois.json directly with json stdlib (STUB-NOTE: lane-A snapshot
loader T008 wires in at phase-PR — same schema, swap one line).

FR-013: unverified POIs are EXCLUDED from the main plan
(`candidates`); they are listed separately under `needs_verification`
("can xac minh"), must-visit flagged (validator decides per FR-031).
FR-024/FR-026: unverified fields (giờ mở cửa/rating/giá/tags) get
`uncertainty` labels and are never presented as fact.

Rules:
- avoid -> always excluded (reason).
- must_visit + verified -> candidates (violations flagged).
- must_visit + unverified -> needs_verification (flagged, NOT main plan).
- other unverified -> needs_verification (reason "chua xac minh").
- type/budget/hours filters apply to candidates as before.
"""

from __future__ import annotations

import json

from BE.app.services import to_min

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


def _overlaps(hours: list[str], ws: int, we: int) -> bool:
    for h in hours or []:
        for interval in h.split(","):
            if interval.count("-") != 1:
                # A stray single-time fragment is not an open interval; skip it as closed.
                continue
            o, c = (part.strip() for part in interval.split("-"))
            try:
                o, c = to_min(o), to_min(c)
            except ValueError:
                continue
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


def uncertainty(p: dict) -> list[str]:
    """FR-024/FR-026 labels for unverified fields (never used as fact)."""
    labels = []
    if not p.get("opening_hours"):
        labels.append("gio mo cua chua xac minh")
    if p.get("rating") is None:
        labels.append("rating chua xac minh")
    if not p.get("tags"):
        labels.append("tags chua xac minh")
    if int(p.get("fee", 0)) == 0 and p.get("type") == "restaurant":
        labels.append("gia chua xac minh")
    return labels


def retrieve(trip: dict, pois: list[dict]) -> dict:
    """Return {"candidates": [{poi_id, reasons[], uncertainty[]}],
    "needs_verification": [{poi_id, reasons[], uncertainty[], must_visit}],
    "excluded": [{poi_id, reason}]}."""
    ws, we = to_min(trip.get("start_time", "07:00")), to_min(trip.get("end_time", "18:00"))
    budget = int(trip.get("budget", 0))
    must = set(trip.get("must_visit", []))
    avoid = set(trip.get("avoid", []))
    types = wanted_types(trip.get("activities", []))
    candidates, needs_verification, excluded = [], [], []
    for p in pois:
        pid = p.get("poi_id")
        if pid in avoid:
            excluded.append({"poi_id": pid, "reason": "avoid"})
            continue
        if not p.get("verified"):
            entry = {"poi_id": pid, "uncertainty": uncertainty(p) + ["poi chua xac minh"],
                     "must_visit": pid in must,
                     "reasons": ["must-visit (cho xac minh, ngoai main plan)"] if pid in must
                     else ["chua xac minh (FR-013)"]}
            needs_verification.append(entry)
            continue
        reasons: list[str] = []
        if pid in must:
            if not _overlaps(p.get("opening_hours", []), ws, we):
                reasons.append("must-visit (ngoai gio mo cua)")
            reasons.append("must-visit")
            candidates.append({"poi_id": pid, "reasons": reasons,
                               "uncertainty": uncertainty(p)})
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
        candidates.append({"poi_id": pid, "reasons": reasons,
                           "uncertainty": uncertainty(p)})
    return {"candidates": candidates, "needs_verification": needs_verification,
            "excluded": excluded}
