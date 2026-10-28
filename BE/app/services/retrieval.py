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
- lodging/transport -> excluded unless must_visit (not a day activity).
- type/budget/hours filters apply to candidates as before.

Activity filter compares the canonical group `cat` (lane-A enum in
pois.json; seed POIs without `cat` fall back to canonical_category(type)),
never the raw SerpApi `type`. Activity text is NFC-normalised and matched
whole-word, longest phrase first; a matched phrase is consumed so its
sub-words cannot match again ("yêu cầu" never reads as "cầu"). Multi-word
phrases also match without diacritics ("tam bien").
"""

from __future__ import annotations

import re
import unicodedata

from BE.app.services import to_min
from BE.common import load_json
from BE.ml.patm.estimate_duration import canonical_category

# Phrase -> canonical groups. An empty list marks a phrase that only
# blocks its sub-words from matching.
ACTIVITY_TYPE_MAP = {
    "biển": ["beach"], "bãi biển": ["beach"], "tắm biển": ["beach"], "tắm": ["beach"],
    "bơi": ["beach"], "lặn": ["beach"], "lướt sóng": ["beach"],
    "núi": ["nature"], "leo núi": ["nature"], "leo": ["nature"],
    "trekking": ["nature"], "rừng": ["nature"], "thác": ["nature"],
    "suối": ["nature"], "đèo": ["nature"], "hang động": ["nature"],
    "cắm trại": ["nature"], "thiên nhiên": ["nature"], "bán đảo": ["nature"],
    "ăn": ["restaurant"], "nhà hàng": ["restaurant"], "hải sản": ["restaurant"],
    "mì": ["restaurant"], "bún": ["restaurant"], "phở": ["restaurant"],
    "ẩm thực": ["restaurant"], "buffet": ["restaurant"],
    "đặc sản": ["restaurant", "market"],
    "quán": ["restaurant", "cafe", "bar"], "quán ăn": ["restaurant"],
    "quán cà phê": ["cafe"], "quán bar": ["bar"], "quán bia": ["bar"],
    "quán nhậu": ["bar"],
    "cà phê": ["cafe"], "cafe": ["cafe"], "coffee": ["cafe"],
    "trà sữa": ["cafe"], "uống trà": ["cafe"], "bánh ngọt": ["cafe"],
    "bar": ["bar"], "pub": ["bar"], "bia": ["bar"], "nhậu": ["bar"],
    "cocktail": ["bar"], "rượu": ["bar"], "karaoke": ["bar"], "club": ["bar"],
    "hộp đêm": ["bar"], "nhạc sống": ["bar"],
    "spa": ["spa"], "massage": ["spa"], "mát xa": ["spa"], "xông hơi": ["spa"],
    "gội đầu": ["spa"], "làm nail": ["spa"],
    "chợ": ["market"], "mua sắm": ["market"], "shopping": ["market"],
    "quà": ["market"], "lưu niệm": ["market"], "siêu thị": ["market"],
    "trung tâm thương mại": ["market"],
    "văn hóa": ["museum"], "bảo tàng": ["museum"], "triển lãm": ["museum"],
    "nghệ thuật": ["museum"], "phòng trưng bày": ["museum"],
    "lịch sử": ["museum", "landmark"],
    "check-in": ["landmark"], "cầu": ["landmark"], "chùa": ["landmark"],
    "nhà thờ": ["landmark"], "đền": ["landmark"], "đình": ["landmark"],
    "ngắm cảnh": ["landmark"], "chụp ảnh": ["landmark"], "sống ảo": ["landmark"],
    "di tích": ["landmark"], "tâm linh": ["landmark"],
    "vui chơi": ["attraction"], "công viên giải trí": ["attraction"],
    "công viên nước": ["attraction"], "thủy cung": ["attraction"],
    "cáp treo": ["attraction"], "du thuyền": ["attraction"],
    "đi thuyền": ["attraction"], "thuyền thúng": ["attraction"],
    "nấu ăn": ["attraction"],
    "công viên": ["park"], "đi dạo": ["park"], "dạo bộ": ["park"],
    "picnic": ["park"],
    "yêu cầu": [], "nhu cầu": [], "gần biển": [], "view biển": [],
}
NON_ACTIVITY_CATS = {"lodging", "transport"}
PAID_CATS = {"restaurant", "cafe", "bar", "spa"}


def load_pois_json(path: str) -> list[dict]:
    """Read a snapshot pois.json (T061c: shares BE.common.load_json)."""
    data = load_json(path)
    return data["pois"] if isinstance(data, dict) else data


def poi_category(p: dict) -> str:
    return p.get("cat") or canonical_category(p.get("type") or "")


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


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return unicodedata.normalize(
        "NFC", "".join(c for c in s if unicodedata.category(c) != "Mn")
    ).replace("đ", "d")


def _consume(text: str, phrase: str) -> tuple[bool, str]:
    pat = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    out, n = re.subn(pat, " | ", text)
    return n > 0, out


_PHRASES = sorted(ACTIVITY_TYPE_MAP, key=len, reverse=True)


def match_activity(text: str) -> set[str]:
    """One activity string -> canonical groups (empty set = not understood)."""
    rest = " ".join(unicodedata.normalize("NFC", text).lower().split())
    out: set[str] = set()
    for ph in _PHRASES:
        hit, rest = _consume(rest, ph)
        if hit:
            out.update(ACTIVITY_TYPE_MAP[ph])
    rest = _plain(rest)
    for ph in _PHRASES:
        if " " in ph:
            hit, rest = _consume(rest, _plain(ph))
            if hit:
                out.update(ACTIVITY_TYPE_MAP[ph])
    return out


def wanted_types(activities: list[str]) -> set[str]:
    out: set[str] = set()
    for a in activities or []:
        out.update(match_activity(a))
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
    if int(p.get("fee", 0)) == 0 and poi_category(p) in PAID_CATS:
        labels.append("gia chua xac minh")
    return labels


def retrieve(trip: dict, pois: list[dict]) -> dict:
    """Return {"candidates": [{poi_id, reasons[], uncertainty[]}],
    "needs_verification": [{poi_id, reasons[], uncertainty[], must_visit}],
    "excluded": [{poi_id, reason}], "unmatched_activities": [str]}."""
    ws, we = to_min(trip.get("start_time", "07:00")), to_min(trip.get("end_time", "18:00"))
    budget = int(trip.get("budget", 0))
    must = set(trip.get("must_visit", []))
    avoid = set(trip.get("avoid", []))
    activities = trip.get("activities", []) or []
    types = wanted_types(activities)
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
        cat = poi_category(p)
        if cat in NON_ACTIVITY_CATS:
            excluded.append({"poi_id": pid, "reason": "khong phai hoat dong"})
            continue
        if types and cat not in types:
            excluded.append({"poi_id": pid, "reason": "khong khop loai hoat dong"})
            continue
        if int(p.get("fee", 0)) > budget:
            excluded.append({"poi_id": pid, "reason": "vuot ngan sach"})
            continue
        if not _overlaps(p.get("opening_hours", []), ws, we):
            excluded.append({"poi_id": pid, "reason": "dong cua trong khung gio"})
            continue
        reasons.append(f"khop loai {cat}")
        candidates.append({"poi_id": pid, "reasons": reasons,
                           "uncertainty": uncertainty(p)})
    return {"candidates": candidates, "needs_verification": needs_verification,
            "excluded": excluded,
            "unmatched_activities": [a for a in activities if not match_activity(a)]}


def retrieve_softened(trip: dict, pois: list[dict]) -> dict:
    """FR-006/FR-022: activities are a soft pref. When they empty the pool,
    drop them once and say so; avoid/verified/budget/hours stay hard.
    Only when the type filter actually ran: unmatched activities filter
    nothing, so an empty pool there is caused by a hard constraint."""
    out = retrieve(trip, pois)
    out["softened"] = []
    if not out["candidates"] and wanted_types(trip.get("activities")):
        unmatched = out["unmatched_activities"]
        out = retrieve(dict(trip, activities=[]), pois)
        out["unmatched_activities"] = unmatched
        out["softened"] = ["activities (bo loc loai, giu avoid+budget)"]
    return out
