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
- type/budget/hours filters apply to candidates as before; the type match
  compares the canonical English category (`soft_rules.poi_category`) — the
  snapshot `type` is a free Vietnamese label and must never be compared with
  the English keys of `ACTIVITY_TYPE_MAP`.
"""

from __future__ import annotations

from BE.app.services import soft_rules, to_min
from BE.app.services.common import effective_fee
from BE.app.services.profile_filter import _match_terms, fold
from BE.common import load_json

# User activity keyword -> canonical English category (soft_rules.poi_category).
# Keys are matched as WHOLE words/phrases (B3: a bare substring let "ăn" hit
# "văn hóa" and "cầu" hit "yêu cầu"); values are canonical categories so the
# type filter compares English to English and never a Vietnamese `type`
# against an English key (B1).
ACTIVITY_TYPE_MAP = {
    "biển": ["beach"], "tắm": ["beach"], "núi": ["nature"], "leo": ["nature"],
    "ăn": ["restaurant"], "mì": ["restaurant"], "quán": ["restaurant", "market"],
    "văn hóa": ["museum"], "bảo tàng": ["museum"], "lịch sử": ["museum"],
    "chợ": ["market"], "mua sắm": ["market"], "check-in": ["landmark"],
    # Bare "cầu" is too ambiguous in Vietnamese ("yêu cầu", "cầu nguyện"):
    # bridges are named instead (Cầu Rồng is the landmark, the rest are
    # attractions in the snapshot).
    "cầu rồng": ["landmark"], "cầu sông hàn": ["attraction"],
}


def load_pois_json(path: str) -> list[dict]:
    """Read a snapshot pois.json (T061c: shares BE.common.load_json)."""
    data = load_json(path)
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
    """Canonical English categories asked for by free-form Vietnamese activities.

    Matching is word-boundary/phrase based (profile_filter semantics), so
    "văn hóa" never contributes "restaurant" through the substring "ăn".
    """
    out: set[str] = set()
    for a in activities or []:
        low = str(a or "").lower()
        folded = fold(low)
        for kw, cats in ACTIVITY_TYPE_MAP.items():
            if _match_terms((kw,), low, folded) is not None:
                out.update(cats)
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
    if (int(p.get("fee", 0)) == 0
            and soft_rules.poi_category(p) == "restaurant"):
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
        if types and soft_rules.poi_category(p) not in types:
            excluded.append({"poi_id": pid, "reason": "khong khop loai hoat dong"})
            continue
        # B5: a POI only eats budget when its price is actually KNOWN
        # (ticket_vnd -> price_band midpoint -> legacy fee). Unknown price is
        # not "free" (no false fact) but also cannot block on a guess.
        fee = effective_fee(p)
        if fee is not None and fee > budget:
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
