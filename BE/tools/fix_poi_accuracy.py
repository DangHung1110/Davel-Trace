"""One accuracy pass over the snapshot (docs/plan-accuracy.md). Idempotent.

Fixes what an audit of 141 real plans found in the data, not in the planner:

- `cat`: temples and churches leave `landmark` (`temple`), gift shops leave
  `market` (`shop`), so a wish for "chùa" or "chợ" can mean what it says and a day
  may hold one bridge and one pagoda.
- `subcat`: the finer kind the duration and time-of-day rules read.
- `plan_tier`: `main` (default plans), `local` and `wish_only` (only when a wish
  asks for it), `excluded` (never, unless it is a must_visit).
- `visit_min`: durations by subcat, Google's "people typically spend" when known.
- `hours_by_day`: Google's weekly table, Monday first, "" = closed that day.
- tickets the web agrees on, and the POIs the pool was missing.

The new POIs have no OSRM row: the matrix borrows the row of the nearest POI plus
the short hop to it, and lists them under `coverage.estimated_ids`. The holdout
below measures what that costs. Re-route them when an OSRM image is at hand.

Usage (repo root):
    python BE/tools/fix_poi_accuracy.py --lookups .claude/verify-old-wip
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import re
import statistics
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from BE.app.services.profile_filter import fold  # noqa: E402
from BE.ml.data.enrich_snapshot import enrich  # noqa: E402
from BE.ml.data.enrich_tags import tag_poi  # noqa: E402
from BE.ml.data.osm_crosscheck import check_poi, markdown, summarize  # noqa: E402
from BE.tools.build_verify_page import row_hash  # noqa: E402

SNAPSHOT = _REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v1"
CHECKED_AT = "2026-10-31"
REVIEWER = "claude-google-maps"

# Below this many Google reviews a sight only comes up when a wish asks for it:
# the plans were full of places no traveller would look for.
MIN_REVIEWS = {"temple": 100, "church": 500, "landmark": 50, "museum": 20, "market": 100,
               "shop": 40, "beach": 100, "park": 100, "viewpoint": 50, "nature": 5,
               "attraction": 30, "restaurant": 30, "cafe": 30, "bar": 30, "spa": 30}

TOURIST_MARKETS = ("cho han", "cho con", "cho dem helio", "cho dem son tra",
                   "pho di bo - cho dem bach dang", "cho dem le duan")
LOCAL_NAMES = ("cong vien cau vuot nga ba hue", "cong vien bien ha khe",
               "bai tam lien chieu", "bai tam nguyen than hien", "bai bien nguyen tat thanh")
EXCLUDED = {
    "huyen khong cave": "nam trong Ngu Hanh Son, da tinh trong diem do",
    "dong am phu": "nam trong Ngu Hanh Son, da tinh trong diem do",
    "dong van thong": "nam trong Ngu Hanh Son, da tinh trong diem do",
    "dong tang chon": "nam trong Ngu Hanh Son, da tinh trong diem do",
    "khu am thuc cho con": "khu an uong trong Cho Con, khong phai cho",
    "nha luu niem chien cong": "chi mo theo doan, phai lien he truoc",
    "mai vang": "vuon tu nhan, phai lien he truoc",
    "nha tho toc ho": "nha tho toc, khong phai diem tham quan",
}
MEDICAL_TYPES = ("Spa y tế", "Thẩm mỹ viện", "Bác sĩ trị liệu xoa bóp")
WISH_ONLY_NAMES = {
    "sun world ba na": "di ca ngay", "vinwonders": "di ca ngay", "cu lao cham": "di ca ngay",
    "mikazuki water park": "hoat dong rieng", "dd wonderland": "khu vui choi tre em",
    "voc glamping": "theo goi doan", "khu du lich sinh thai lai thieu": "hoat dong rieng",
    "khu du lich sinh thai suoi hoa": "hoat dong rieng", "dich vu cano": "hoat dong rieng",
    "rung dua bay mau": "ngoai Da Nang", "tham quan rung dua": "ngoai Da Nang",
    "thuyen thung": "ngoai Da Nang", "dich vu thuyen thung": "ngoai Da Nang",
    "diem don khach du lich thuyen thung": "ngoai Da Nang",
    "lang da my nghe non nuoc": "chua co danh gia", "lang nuoc mam nam o": "chua co danh gia",
}

# (p25, p50, p75) minutes. Google's "people typically spend" where it answered
# (19 POIs, 30-31/10/2026); p50 stays inside Google's range.
GOOGLE_TYPICAL = {
    "ChIJEymIkTYYQjERWO-pgjkKGMk": (45, 65, 90),
    "ChIJt1wLHjEYQjEREA1YGZU2yOc": (45, 60, 120),
    "ChIJcVJkUPcXQjERsA8_dfySw5E": (30, 90, 150),
    "ChIJpRFvp6sZQjERY_CDfnMCx2w": (15, 25, 40),
    "ChIJD4Ge5WQZQjERW-0GhLbS310": (15, 45, 90),
    "ChIJFYLgeggZQjERgwxGcK7JcpQ": (10, 20, 25),
    "ChIJ-VaWslgZQjERwaL3uKR9fB4": (60, 90, 120),
    "ChIJ78thjjYYQjERkiy-c9ebVPE": (30, 60, 90),
    "ChIJjaiK7LgZQjERSQvPDP9gnVQ": (45, 60, 90),
    "ChIJXeXlix8ZQjERx9QsmNqx6_U": (45, 60, 150),
    "ChIJLWoAs80ZQjERLKHDYD-ZymI": (30, 60, 90),
    "ChIJ8VYU_wQRQjER1lJ6MdGSHjg": (10, 30, 45),
    "ChIJJZ47gFgZQjERvHYpZqPp0lU": (10, 15, 30),
    "ChIJx6-KGnIXQjER7x-T0zeOlBw": (60, 75, 120),
    "ChIJmQ0KGkE9QjER4TyQDQ_04TA": (45, 60, 120),
    "ChIJRaHks2wXQjERVMrWhffmRXw": (45, 70, 90),
    "ChIJ2y5L4dQNQjERxeSLc68fbrw": (60, 90, 120),
    "ChIJySI1VxkXQjERUSItJZQgxBE": (60, 75, 120),
    "ChIJBcr6kegZQjER2nCllYpT_Qc": (20, 60, 90),
    "manual:cau-tinh-yeu": (10, 20, 30),
    "manual:be-man": (25, 70, 120),
    "manual:banh-xeo-ba-duong": (30, 45, 60),
    "manual:golden-pine": (25, 90, 150),
    "manual:sky36": (20, 45, 90),
}
# Long visits the category rule cannot know. General knowledge of each place,
# marked `curated` in dur_source so nobody reads them as measured.
NAMED_DURATION = {
    "sun world ba na": (300, 420, 540), "vinwonders": (300, 420, 540),
    "cu lao cham": (360, 480, 540), "mikazuki water park": (120, 180, 240),
    "trung tam giai tri helio": (60, 120, 180), "suoi luong": (120, 180, 240),
    "khu du lich sinh thai": (90, 150, 210), "voc glamping": (120, 180, 240),
    "dd wonderland": (60, 120, 180), "khu pho du lich an thuong": (45, 60, 120),
    "khu du lich nam o": (45, 75, 120), "lang da my nghe": (30, 60, 90),
    "lang nuoc mam": (20, 40, 60), "nhat lam thuy": (45, 60, 90),
    "dich vu cano": (120, 180, 240), "rung dua": (45, 75, 120),
    "tham quan rung dua": (45, 75, 120), "thuyen thung": (45, 75, 120),
    "dich vu thuyen thung": (45, 75, 120), "diem don khach du lich thuyen thung": (45, 75, 120),
    "du thuyen": (45, 60, 75), "ben du thuyen": (45, 60, 75),
    "hai van quan": (20, 40, 60), "ghenh bang": (45, 75, 120), "lang bich hoa": (20, 40, 60),
    "hai dang tien sa": (15, 30, 45), "khu can cu": (30, 60, 90),
    "ban dao son tra": (120, 180, 240), "nui son tra": (90, 150, 210),
    "ho hoa trung": (60, 120, 180), "suoi lac": (90, 150, 210),
    "khu du lich ben nam yen": (60, 120, 180), "son tra tinh vien": (30, 60, 90),
    "duong hoa bach dang": (15, 30, 45), "cong vien 29/3": (30, 60, 90),
    "cho han": (30, 60, 90), "cho con": (30, 60, 90),
}
SUBCAT_DURATION = {
    "church": (10, 20, 30), "major_temple": (30, 50, 75), "pagoda": (15, 30, 45),
    "bridge": (10, 20, 30), "statue": (10, 20, 25), "night_market": (30, 60, 90),
    "day_market": (15, 30, 45), "eatery": (25, 40, 60), "hotpot_bbq": (60, 90, 120),
}
CAT_DURATION = {
    "temple": (15, 30, 45), "landmark": (15, 30, 45), "market": (15, 30, 45), "shop": (15, 25, 40),
    "museum": (30, 60, 90), "attraction": (90, 150, 210), "beach": (60, 100, 150),
    "park": (30, 45, 75), "viewpoint": (20, 40, 60), "nature": (90, 150, 210),
    "restaurant": (60, 75, 105), "cafe": (45, 60, 120), "bar": (60, 90, 150), "spa": (60, 90, 120),
}

# Prices the web agrees on (docs/plan-accuracy.md lists the sources).
TICKETS = {
    "ChIJ2y5L4dQNQjERxeSLc68fbrw": (40_000, "Thuy Son 40k/nguoi; thang may them 15k"),
    "ChIJyUQ4aw72QTERCXl5YV-4U1w": (1_000_000, "cap treo khu hoi 1 trieu/nguoi lon, nam 2026"),
}
# Free to enter, whatever the band says.
NO_TICKET_NAMES = ("nha bia chung tich", "bao tang van hoa phat giao")

NEW_POIS = [
    {"poi_id": "manual:cau-tinh-yeu", "name": "Cầu Tình Yêu", "type": "Thắng cảnh", "cat": "landmark",
     "lat": 16.0629967, "lon": 108.2298146, "rating": 4.6, "review_count": 792,
     "opening_hours": ["00:00-23:59"], "like": "Cầu Rồng", "band": "cheap",
     "note": "Google Maps: Cầu Tình Yêu - Love Pier. Mọi người thường dành tối đa 30 phút."},
    {"poi_id": "manual:ca-chep-hoa-rong", "name": "Tượng Cá Chép Hóa Rồng", "type": "Tượng đài", "cat": "landmark",
     "lat": 16.0629054, "lon": 108.2298191, "rating": 4.5, "review_count": 1486,
     "opening_hours": ["00:00-23:59"], "like": "Cầu Rồng", "band": "cheap",
     "note": "Google Maps: Tượng Cá Chép Hóa Rồng, ngoài trời, tự do."},
    {"poi_id": "manual:nha-tho-con-ga", "name": "Nhà thờ Con Gà (Giáo xứ Chính Tòa Đà Nẵng)",
     "type": "Nhà thờ Công giáo", "cat": "temple", "lat": 16.0666672, "lon": 108.2231873,
     "rating": 4.3, "review_count": 2756, "opening_hours": [], "like": "Chùa Linh Ứng", "band": "cheap",
     "note": "Google Maps: Giáo Xứ Chính Toà Đà Nẵng, 156 Trần Phú. Giờ chưa đầy đủ: dùng khung an toàn."},
    {"poi_id": "manual:bai-tam-pham-van-dong", "name": "Bãi tắm Phạm Văn Đồng", "type": "Bãi biển", "cat": "beach",
     "lat": 16.0732782, "lon": 108.2468342, "rating": None, "review_count": None,
     "opening_hours": ["00:00-23:59"], "like": "Bãi biển Mỹ Khê", "band": "cheap",
     "note": "Google Maps: Bãi tắm Phạm Văn Đồng. Chưa đọc được số đánh giá."},
    {"poi_id": "manual:be-man", "name": "Hải Sản Bé Mặn", "type": "Nhà hàng hải sản", "cat": "restaurant",
     "lat": 16.0820695, "lon": 108.2473865, "rating": 3.7, "review_count": 7875,
     "opening_hours": [], "like": "Mộc quán Seafood", "band": "medium",
     "note": "Google: 3,7★, 7.875 đánh giá, thường dành 25 phút đến 2 giờ. Giờ chưa đầy đủ."},
    {"poi_id": "manual:banh-xeo-ba-duong", "name": "Bánh Xèo Bà Dưỡng", "type": "Quán ăn nhỏ", "cat": "restaurant",
     "lat": 16.0588772, "lon": 108.216166, "rating": 4.3, "review_count": 10849,
     "opening_hours": ["10:00-21:30"], "like": "Mì Quảng Ếch", "band": "cheap", "ticket_note": "100-200k/nguoi",
     "fee": 150_000,
     "note": "Google: 4,3★, 10.849 đánh giá, giá mỗi người 100-200k, đóng cửa 21:30, thường dành 45 phút."},
    {"poi_id": "manual:golden-pine", "name": "New Golden Pine Club", "type": "Hộp đêm", "cat": "bar",
     "lat": 16.0742601, "lon": 108.2290869, "rating": 4.2, "review_count": 2779,
     "opening_hours": [], "like": "On The Radio", "band": "medium",
     "note": "Google: 4,2★, 2.779 đánh giá, thường dành 25 phút đến 2,5 giờ. Giờ mở chưa đầy đủ."},
    {"poi_id": "manual:sky36", "name": "Sky36", "type": "Quán bar", "cat": "bar",
     "lat": 16.0771856, "lon": 108.2238351, "rating": 4.3, "review_count": 3213,
     "opening_hours": [], "like": "On The Radio", "band": "expensive",
     "note": "Google: 4,3★, 3.213 đánh giá, đóng cửa 02:00. Giờ mở chưa đầy đủ."},
]


def _name(poi: dict) -> str:
    return fold(str(poi.get("name") or ""))


def _starts(poi: dict, *prefixes: str) -> bool:
    return _name(poi).startswith(prefixes)


def _is_temple(poi: dict) -> bool:
    name, kind = _name(poi), fold(str(poi.get("type") or ""))
    return (kind.startswith(("chua phat giao", "co so tho tu", "nha tho cong giao", "dien tho"))
            or name.startswith(("chua ", "thien vien", "quoc tu", "nha tho", "giao xu", "dinh ",
                                "den ", "lam ty ni")))


def _is_shop(poi: dict) -> bool:
    kind = fold(str(poi.get("type") or ""))
    return "cua hang" in kind or _starts(poi, "sieu thi dac san")


def assign_cat(poi: dict) -> None:
    cat = poi.get("cat")
    if _starts(poi, "nha bia chung tich", "tuong phat da"):
        poi["cat"] = "landmark"
    elif _starts(poi, "nha tho toc"):
        poi["cat"] = "temple"
    elif cat == "landmark" and _is_temple(poi):
        poi["cat"] = "temple"
    elif cat == "market" and _is_shop(poi):
        poi["cat"] = "shop"
    elif cat == "cafe" and "diem ngam canh" in fold(str(poi.get("type") or "")):
        poi["cat"] = "viewpoint"


def assign_subcat(poi: dict) -> None:
    cat, name, kind = poi.get("cat"), _name(poi), fold(str(poi.get("type") or ""))
    subcat = None
    if cat == "temple":
        if name.startswith(("nha tho", "giao xu")) or "nha tho cong giao" in kind:
            subcat = "church"
        elif (poi.get("review_count") or 0) >= 1000:
            subcat = "major_temple"
        else:
            subcat = "pagoda"
    elif cat == "landmark":
        if name.startswith("cau ") or kind == "cau":
            subcat = "bridge"
        elif re.search(r"\b(tuong|nha bia|dai tuong niem)\b", name) or kind in ("tuong dai", "dai tuong niem"):
            subcat = "statue"
    elif cat == "market":
        subcat = "night_market" if "cho dem" in name or "night market" in name else "day_market"
    elif cat == "restaurant":
        if re.search(r"\b(lau|hot pot|hotpot|nuong|bbq|buffet|yakiniku)\b", f"{name} {kind}"):
            subcat = "hotpot_bbq"
        elif kind in ("quan mi", "quan an nho") or re.search(r"\b(mi|my) quang\b|^(quan )?(bun|pho|com|banh) ", name):
            subcat = "eatery"
    elif cat == "viewpoint":
        if "binh minh" in name or "sunrise" in name:
            subcat = "sunrise"
        elif "hoang hon" in name or "sunset" in name:
            subcat = "sunset"
    if subcat:
        poi["subcat"] = subcat
    else:
        poi.pop("subcat", None)


def assign_tier(poi: dict) -> None:
    cat, reviews = poi.get("cat"), poi.get("review_count")
    tier, why = "main", None
    for prefix, reason in EXCLUDED.items():
        if _starts(poi, prefix):
            tier, why = "excluded", reason
    if poi.get("type") in MEDICAL_TYPES:
        tier, why = "excluded", "co so y te hoac tham my, khong phai diem du lich"
    if tier == "main":
        for prefix, reason in WISH_ONLY_NAMES.items():
            if _starts(poi, prefix):
                tier, why = "wish_only", reason
        if poi.get("type") == "Lớp học nấu ăn":
            tier, why = "wish_only", "lop hoc, chi xep khi duoc hoi"
    if tier == "main" and cat == "shop":
        tier, why = "wish_only", "mua qua la viec khach chon, khong phai diem cua moi ngay"
    if tier == "main" and cat == "market" and not _starts(poi, *TOURIST_MARKETS):
        tier, why = "local", "cho dan sinh"
    if tier == "main" and _starts(poi, *LOCAL_NAMES):
        tier, why = "local", "diem cua nguoi dia phuong"
    if tier == "main":
        floor = MIN_REVIEWS.get("church" if poi.get("subcat") == "church" else cat)
        new = str(poi.get("poi_id")).startswith("manual:") and cat == "beach"
        if floor is not None and (reviews or 0) < floor and not new:
            tier, why = "local", f"duoi {floor} danh gia"
    poi["plan_tier"] = tier
    if why:
        poi["plan_tier_reason"] = why
    else:
        poi.pop("plan_tier_reason", None)


def assign_duration(poi: dict) -> None:
    pid, name = poi.get("poi_id"), _name(poi)
    if poi.get("dur_source") == "human":
        return
    source, row = "subcat_rule", None
    if pid in GOOGLE_TYPICAL:
        source, row = "google_typical", GOOGLE_TYPICAL[pid]
    else:
        for prefix, value in NAMED_DURATION.items():
            if name.startswith(prefix):
                source, row = "curated", value
                break
    if row is None and poi.get("type") == "Lớp học nấu ăn":
        source, row = "curated", (150, 210, 240)
    if row is None:
        row = SUBCAT_DURATION.get(poi.get("subcat")) or CAT_DURATION.get(poi.get("cat"))
    if row is None:
        return
    poi["visit_min"] = {"p25": row[0], "p50": row[1], "p75": row[2]}
    poi["dur_source"] = source
    poi["dur_confidence"] = "medium" if source == "google_typical" else "low"


DAY_INDEX = {"T2": 0, "T3": 1, "T4": 2, "T5": 3, "T6": 4, "T7": 5, "CN": 6, "Thứ Hai": 0, "Thứ Ba": 1,
             "Thứ Tư": 2, "Thứ Năm": 3, "Thứ Sáu": 4, "Thứ Bảy": 5, "Chủ Nhật": 6}


def _hhmm(text: str) -> str:
    hour, minute = text.split(":")
    return f"{int(hour):02d}:{minute}"


def parse_day(text: str) -> str | None:
    """One Google day: "07:00 đến 17:30" -> "07:00-17:30", closed -> "", junk -> None."""
    if re.search(r"đóng cửa|closed", text, re.I):
        return ""
    if re.search(r"24 giờ|cả ngày|24 hours", text, re.I):
        return "00:00-23:59"
    spans = re.findall(r"(\d{1,2}:\d{2})\s*(?:đến|–|-|to)\s*(\d{1,2}:\d{2})", text)
    return ", ".join(f"{_hhmm(a)}-{_hhmm(b)}" for a, b in spans) or None


def parse_week(rows: list | None) -> list[str] | None:
    """Google's weekly table -> 7 strings, Monday first; None unless all 7 days read."""
    week: dict[int, str] = {}
    for row in rows or []:
        hit = re.match(r"\s*(T[2-7]|CN|Thứ Hai|Thứ Ba|Thứ Tư|Thứ Năm|Thứ Sáu|Thứ Bảy|Chủ Nhật)\s*[=,:]\s*(.+)", str(row))
        if hit:
            day = parse_day(hit.group(2))
            if day is not None:
                week[DAY_INDEX[hit.group(1)]] = day
    return [week[d] for d in range(7)] if len(week) == 7 else None


def load_weeks(folder: Path) -> dict[str, list[str]]:
    weeks: dict[str, list[str]] = {}
    raw = folder / "old_google_raw.json"
    if raw.exists():
        for pid, row in json.loads(raw.read_text(encoding="utf-8")).items():
            week = parse_week(row.get("h"))
            if week:
                weeks[pid] = week
    drafts = folder / "queue_drafts.jsonl"
    if drafts.exists():
        for line in drafts.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            week = parse_week((row.get("google") or {}).get("hours"))
            if week and row.get("poi_id"):
                weeks[row["poi_id"]] = week
    return weeks


def new_poi(spec: dict, pois: list[dict]) -> dict:
    """A manual POI: the shape of a reviewed neighbour, its labels from the same
    pipeline every POI went through. A neighbour's audit label or "must-go" is not
    evidence about this place."""
    like = next(p for p in pois if p.get("verified") and str(p.get("name")).startswith(spec["like"]))
    poi = copy.deepcopy(like)
    for key in ("pros", "cons", "osm_evidence", "ticket_vnd", "ticket_note", "price_sources", "subcat",
                "plan_tier", "plan_tier_reason", "hours_by_day", "web_evidence", "io_label"):
        poi.pop(key, None)
    poi.update({key: spec[key] for key in ("poi_id", "name", "type", "cat", "lat", "lon", "rating",
                                           "review_count", "opening_hours")})
    poi.update({"tags": [spec["type"]], "source": "manual+web", "fetched_at": CHECKED_AT, "verified": True,
                "verified_at": CHECKED_AT, "verified_by": "claude-google-maps-v1", "hours_source": REVIEWER,
                "fee": int(spec.get("fee") or 0),
                "price_level": {"cheap": 1, "medium": 2, "expensive": 3}[spec["band"]]})
    assign_subcat(poi)
    assign_duration(poi)
    poi["smart_tags"], poi["smart_tag_source"] = tag_poi(poi)
    poi["smart_tags"].update({"price_band": spec["band"], "ticket": False, "band_verified": True})
    enrich([poi], {})
    if spec.get("ticket_note"):
        poi["ticket_note"] = spec["ticket_note"]
    poi["review"] = {"verdict": "dung", "edits": [], "by": [
        {"reviewer": REVIEWER, "ts": f"{CHECKED_AT}T12:00:00.000Z", "note": spec["note"],
         "file": "docs/plan-accuracy.md", "draft_by": f"{REVIEWER}@{CHECKED_AT}"}]}
    return poi


def _distance_km(a: dict, b: dict) -> float:
    dy = (a["lat"] - b["lat"]) * 111.32
    dx = (a["lon"] - b["lon"]) * 111.32 * math.cos(math.radians(a["lat"]))
    return math.hypot(dx, dy)


OSM_NOT_RUN = "not_run"
HOP_SPEED_KM_MIN = 25 / 60   # city motorbike, the hop to the neighbour only
HOP_DETOUR = 1.3             # road length over straight line


def extend_matrix(doc: dict, new: list[dict], by_id: dict) -> list[str]:
    """Borrow the nearest POI's row and column for each POI the matrix lacks."""
    ids, minutes, km = doc["ids"], doc["minutes"], doc["km"]
    added = []
    for poi in new:
        if poi["poi_id"] in ids:
            continue
        routed = [pid for pid in ids if pid in by_id and by_id[pid].get("lat") is not None
                  and pid not in added]
        near = min(routed, key=lambda pid: _distance_km(poi, by_id[pid]))
        hop_km = round(_distance_km(poi, by_id[near]) * HOP_DETOUR, 2)
        hop_min = max(1, round(hop_km / HOP_SPEED_KM_MIN))
        k = ids.index(near)
        n = len(ids)
        row_min = [None if v is None else v + hop_min for v in minutes[k]]
        row_km = [None if v is None else round(v + hop_km, 2) for v in km[k]]
        for i in range(n):
            minutes[i].append(None if minutes[i][k] is None else minutes[i][k] + hop_min)
            km[i].append(None if km[i][k] is None else round(km[i][k] + hop_km, 2))
        row_min[k], row_km[k] = hop_min, hop_km
        minutes[k][n], km[k][n] = hop_min, hop_km
        minutes.append(row_min + [0])
        km.append(row_km + [0.0])
        ids.append(poi["poi_id"])
        added.append(poi["poi_id"])
        print(f"  matrix: {poi['name'][:28]} borrows {by_id[near]['name'][:30]} ({hop_km} km, {hop_min} min)")
    if added:
        doc["n"] = len(ids)
        coverage = doc.setdefault("coverage", {})
        coverage["estimated_ids"] = sorted(set(coverage.get("estimated_ids") or []) | set(added))
        coverage["pairs_total"] = coverage["cells"] = len(ids) * len(ids)
    return added


def holdout(doc: dict, by_id: dict, limit_km: float = 0.6, sample: int = 120) -> None:
    """What borrowing a row costs, measured on POIs that do have an OSRM row."""
    ids, minutes = doc["ids"], doc["minutes"]
    index = {pid: i for i, pid in enumerate(ids)}
    rng = random.Random(20261031)
    errors, hops = [], []
    usable = [pid for pid in ids if by_id.get(pid, {}).get("lat") is not None]
    for pid in rng.sample(usable, min(sample, len(usable))):
        poi = by_id[pid]
        near = min((q for q in usable if q != pid), key=lambda q: _distance_km(poi, by_id[q]))
        dist = _distance_km(poi, by_id[near])
        if dist > limit_km:
            continue
        hops.append(dist)
        hop = max(1, round(dist * HOP_DETOUR / HOP_SPEED_KM_MIN))
        i, k = index[pid], index[near]
        for other in rng.sample(usable, 80):
            j = index[other]
            if minutes[i][j] and minutes[k][j] and minutes[i][j] >= 3:
                errors.append(abs(minutes[k][j] + hop - minutes[i][j]))
    if errors:
        errors.sort()
        print(f"  holdout: {len(hops)} POIs within {limit_km} km of a neighbour, {len(errors)} legs, "
              f"absolute error median {statistics.median(errors)} min, p90 {errors[int(0.9 * len(errors))]} min")


def write_dense(path: Path, doc: dict) -> None:
    """Same layout as build_poi_matrix.write_matrix: one row per line."""
    lines = ["{"]
    for key, value in doc.items():
        if key not in ("minutes", "km"):
            lines.append(f" {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},")
    for key in ("minutes", "km"):
        lines.append(f' "{key}": [')
        lines.append(",\n".join(f"  {json.dumps(row, separators=(',', ':'))}" for row in doc[key]))
        lines.append(" ]," if key == "minutes" else " ]")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def refresh_osm_sidecar(snapshot: Path, pois: list[dict]) -> None:
    """Re-read the kept OSM matches under the new categories. The pbf is not at hand,
    so a POI added since the OSM run gets a `single` row that says it was not compared."""
    path = snapshot / "osm_crosscheck.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = {}
    for poi in pois:
        kept = doc["pois"].get(poi["poi_id"]) or {}
        row = check_poi(poi, kept.get("match"))
        if not kept or OSM_NOT_RUN in kept.get("evidence", {}):
            row["evidence"][OSM_NOT_RUN] = "added after the OSM run; re-run osm_crosscheck with the pbf"
        if kept.get("duplicate_of"):
            row["duplicate_of"] = kept["duplicate_of"]
        rows[poi["poi_id"]] = row
    doc["pois"], doc["summary"] = rows, summarize(pois, rows)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (snapshot / "OSM_CROSSCHECK.md").write_text(markdown(doc["summary"], pois, rows, doc["meta"]), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--lookups", type=Path, default=None,
                        help="folder with the kept Google lookups (weekly hours)")
    args = parser.parse_args(argv)

    pois_path, matrix_path = args.snapshot / "pois.json", args.snapshot / "matrix.json"
    data = json.loads(pois_path.read_text(encoding="utf-8"))
    pois = data["pois"]
    have = {p["poi_id"] for p in pois}
    created = [new_poi(spec, pois) for spec in NEW_POIS if spec["poi_id"] not in have]
    pois.extend(created)
    data["count"] = int(data.get("count") or 0) + len(created)

    weeks = load_weeks(args.lookups) if args.lookups else {}
    changed = {"cat": 0, "visit_min": 0, "tier": 0, "hours_by_day": 0, "ticket": 0}
    for poi in pois:
        before = row_hash(poi)
        old_cat, old_visit, old_tier = poi.get("cat"), poi.get("visit_min"), poi.get("plan_tier")
        if poi.get("verified"):
            assign_cat(poi)
            assign_subcat(poi)
            assign_tier(poi)
            assign_duration(poi)
            if poi["poi_id"] in TICKETS:
                price, note = TICKETS[poi["poi_id"]]
                if poi.get("ticket_vnd") != price:
                    changed["ticket"] += 1
                poi.update({"ticket_vnd": price, "fee": price, "ticket_note": note})
                poi.setdefault("smart_tags", {})["ticket"] = True
            if _starts(poi, *NO_TICKET_NAMES):
                poi.setdefault("smart_tags", {})["ticket"] = False
            if poi["poi_id"] in weeks:
                changed["hours_by_day"] += poi.get("hours_by_day") != weeks[poi["poi_id"]]
                poi["hours_by_day"] = weeks[poi["poi_id"]]
        changed["cat"] += poi.get("cat") != old_cat
        changed["visit_min"] += poi.get("visit_min") != old_visit
        changed["tier"] += poi.get("plan_tier") != old_tier
        review = poi.get("review") or {}
        if review.get("row_hash") == before:
            review["row_hash"] = row_hash(poi)
        elif poi.get("review") and not review.get("row_hash"):
            review["row_hash"] = row_hash(poi)
    print("changed:", changed, "| new POIs:", len(created))

    doc = json.loads(matrix_path.read_text(encoding="utf-8"))
    by_id = {p["poi_id"]: p for p in pois}
    holdout(doc, by_id)
    added = extend_matrix(doc, pois, by_id)
    pois_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if added:
        write_dense(matrix_path, doc)
    refresh_osm_sidecar(args.snapshot, pois)
    print("matrix ids:", len(doc["ids"]), "| added:", len(added))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
