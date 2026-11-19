"""Build snapshot `danang-v2` (format v2.3) from `danang-v1` + `BE/data/sources/`.

    python BE/ml/data/migrate_v2.py

Reads, never writes, `BE/data/snapshots/danang-v1/` (the reviewed 750-POI
snapshot of `main`) and the dated source files in `BE/data/sources/`.
Writes:

- `BE/data/snapshots/danang-v2/pois.json`             kept POIs, v2.3 records (docs/travelagent/DATA_SPEC.md)
- `BE/data/snapshots/danang-v2/dropped.json`          every POI not kept, with one reason
- `BE/data/snapshots/danang-v2/quarantine_google.json` Google-derived values of the kept POIs
- `BE/data/exports/danang-v2/*.csv`                    training-safe tables (no Google)
- `reports/p0/*`                                       build summary, dropped list, verify queue

The travel matrix is built by `BE/tools/build_matrix_v2.py`, not here.

Rules of the build (DATA_SPEC.md section 1):

- one concept = one field; an estimate is labelled `verified_by = inferred`;
- every value carries `provenance.<group>` (source, verified_by, confidence);
- `pois.json` never holds a Google value: those go to `quarantine_google.json`;
  Google values may only decide whether a POI is kept (`curate_v2.py`);
- user decisions (`decisions_*.json`, `human_verify_v2_*.json`) win over rules.

The build is deterministic: same inputs, same bytes.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import html
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v2_rules as R  # noqa: E402
import curate_v2 as C  # noqa: E402

TODAY = "2026-11-19"
DATA_VERSION = "v2.3"

# DATA_SPEC.md section 2: the ONLY top-level keys of a v2.2 POI (rule 11).
V22_KEYS = (
    "poi_id", "name", "name_raw", "name_en", "lat", "lon",
    "category", "role", "status", "status_reason", "zone", "cluster_id", "alt_group",
    "requires_ticket_of", "hours", "price", "dwell", "tags", "time_profile",
    "popularity", "description", "ext_ids", "provenance",
    "data_version", "valid_from", "valid_to",
)
PROVENANCE_KEYS = ("name", "location", "category", "status", "hours", "price", "dwell",
                   "tags", "popularity")
TAG_KEYS = ("indoor", "effort", "kid_friendly", "party", "good_times", "time_budget",
            "on_request", "sun_exposure", "outdoor_exposure", "rain_cover", "weather_sensitive")
HOURS_KEYS = ("open", "kind", "closed_days", "access_window", "archetype")
PRICE_KEYS = ("tier", "min_vnd", "max_vnd", "note")
POPULARITY_KEYS = ("signature", "audience", "prize_prior", "wikidata_sitelinks",
                   "wikipedia_views_90d")
EXT_KEYS = ("osm", "wikidata", "overture", "google_place_id")

VERIFIED_BY = ("human", "open_data", "user", "agent_web", "inferred")
CONF = {"human": 0.9, "open_data": 0.7, "user": 0.7, "agent_web": 0.6, "inferred": 0.45}
FIXED_HOURS_BY = ("human", "open_data", "user", "agent_web")
PARTIES = ("solo", "couple", "family", "group")
GOOD_TIMES = ("sunrise", "morning", "sunset", "night")
TIME_BUDGETS = ("quick", "half_day", "full_day")
AUDIENCES = ("tourist", "local")
RAIN_COVERS = ("enclosed", "mixed", "open")
QUICK_MAX_MIN, HALF_DAY_MAX_MIN = 45, 240     # `tags.time_budget` bands of `dwell.p50`


def time_budget_of(p50: int) -> str:
    """`tags.time_budget` from the median visit length (minutes)."""
    return "quick" if p50 <= QUICK_MAX_MIN else ("half_day" if p50 <= HALF_DAY_MAX_MIN else "full_day")

GOOGLE_SOURCE = "serpapi/google-maps"
# v1 fields that are Google content: never in pois.json, only in quarantine.
GOOGLE_FIELDS = ("rating", "review_count", "price_level", "type", "ambience", "pros", "cons")
# v1 `hours_source` values whose hours were read off Google Maps.
GOOGLE_HOURS_SOURCES = ("claude-google-maps", "claude-google-maps-v1")
OPEN_SPACE_HOURS = ("rule_open_access", "inferred")

CLUSTERS = {
    # cluster_id: (parent name, anchor name, radius m)
    "ba_na": ("Sun World Bà Nà Hills", "Ba Na Hills", 1500),
    "ngu_hanh_son": ("Ngũ Hành Sơn", "Hòn Thủy Sơn", 800),
    "bay_mau": ("Rừng Dừa Bảy Mẫu", "Rừng Dừa Bảy Mẫu", 1000),
}
# Inside the Thủy Sơn ticket gate (reviewer judgement, needs human check).
NHS_TICKETED = {"Động Tàng Chơn", "Huyen Khong Cave", "Động Vân Thông",
                "Quốc Tự Tam Thai", "Hòn Thủy Sơn"}
OLD_TOWN_PARENT, OLD_TOWN_ANCHOR = "Phố cổ Hội An", "Chùa Cầu"
SIGNATURE_EXTRA = {"Sun World Bà Nà Hills", "Cầu Rồng", "Bãi biển Mỹ Khê", "Ngũ Hành Sơn",
                   "Chợ Hàn", "Chợ Cồn", "Hải đăng Tiên Sa", "Cù Lao Chàm",
                   "VinWonders Nam Hội An", "Đèo Hải Vân", "Hải Vân Quan",
                   "Rừng Dừa Bảy Mẫu", "Phố đi bộ - chợ đêm Bạch Đằng Đà Nẵng",
                   "Phố cổ Hội An", "Chùa Cầu", "Thánh địa Mỹ Sơn", "Cầu Vàng",
                   "Làng rau Trà Quế", "Chợ đêm Hội An", "Cầu Tình Yêu",
                   "Tượng Cá Chép Hóa Rồng"}
OSM_CAT = {"restaurant": "restaurant", "fast_food": "restaurant", "cafe": "cafe",
           "bar": "nightlife", "pub": "nightlife", "marketplace": "day_market",
           "museum": "museum_indoor", "place_of_worship": "religious", "park": "outdoor_landmark",
           "beach": "beach", "viewpoint": "viewpoint", "theme_park": "paid_attraction",
           "attraction": "outdoor_landmark", "gallery": "museum_indoor"}
# v1 `plan_tier` -> v2.2: excluded -> status, wish_only -> tags.on_request,
# main/local -> popularity.audience. "ngoai Da Nang" (Hội An) is in scope now.
OUT_OF_SCOPE_REASON = "ngoai Da Nang"
# Category-level clean ranking prior (no Google input), DATA_SPEC.md section 3.
CATEGORY_PRIOR = {
    "beach": 0.6, "viewpoint": 0.55, "outdoor_landmark": 0.5, "religious": 0.45,
    "museum_indoor": 0.5, "day_market": 0.5, "night_market": 0.55, "paid_attraction": 0.55,
    "restaurant": 0.45, "cafe": 0.4, "nightlife": 0.35, "wellness": 0.3, "lodging": 0.0,
}
LOCAL_PENALTY = 0.1
# Effort (1 light .. 3 heavy) of a POI without a v1 `intensity`, by dwell kind.
EFFORT_BY_KIND = {"nature": 2, "viewpoint": 2, "beach": 2, "theme_park_big": 2,
                  "island_day_trip": 2, "heritage_site": 2, "old_town": 2, "eco_park": 2,
                  "water_park": 2}
ON_REQUEST_KINDS = ("cooking_class", "shop", "theme_park_big", "island_day_trip")

# v1 review note (may quote Google ratings) -> clean short reason. The full
# note goes to quarantine as `review_note_v1`. First match wins; `{}` takes
# the first captured place name.
REASON_RULES = (
    (r"tiếp viên", "quán có tiếp viên — không hợp lịch trình du lịch"),
    (r"karaoke", "karaoke — không phải điểm đến cho khách du lịch"),
    (r"tiệc cưới|hội nghị", "trung tâm tiệc cưới, hội nghị — không phải nơi khách ghé ăn"),
    (r"nặn mụn|liệu trình", "chăm sóc da theo liệu trình — không phải spa thư giãn"),
    (r"đóng vĩnh viễn|[Tt]ạm thời đóng cửa|[Kk]hông còn trên Google|không còn mở ra",
     "đã đóng cửa hoặc không còn hoạt động"),
    (r"cùng một vé cáp treo", "nằm trong khu Sun World Bà Nà (cùng vé) — gộp vào POI Sun World"),
    (r"[Tt]rùng[^']{0,40}'(.+?)'(?=[\s,.;:)]|$)|(?:gộp vào|trong khuôn viên|Cổng của) '(.+?)'(?=[\s,.;:)]|$)",
     "trùng hoặc nằm trong '{}'"),
    (r"[Tt]rùng", "trùng hoặc gộp với điểm khác"),
    (r"điểm khách dừng là '([^']+)'|điểm chính là ([^;(.]+?)\s*[(;.]",
     "chỉ là một phần của '{}' — xếp điểm chính"),
    (r"Điểm tham quan thật là '([^']+)'", "không phải điểm tham quan (điểm thật '{}' chưa có)"),
    (r"giờ lễ", "nhà thờ giáo xứ chỉ có giờ lễ, không có giờ tham quan"),
    (r"[Tt]ọa độ sai", "toạ độ sai — cần nhập lại"),
    (r"không có cơ sở này|[Kk]hông xác nhận được", "không xác nhận được cơ sở tại toạ độ này"),
    (r"Chỉ có trên OSM|Tên OSM|[Tt]ên chung chung|tên riêng|Tên là câu mô tả",
     "tên chung chung hoặc chỉ có trên OSM — không đủ nguồn xác nhận"),
    (r"không phải|Am thờ|Khu nghỉ chân|Đơn vị tổ chức tour|chợ dân sinh",
     "không phải điểm đến du lịch"),
    (r"đổi tên", "địa điểm đã đổi tên hoặc đổi chủ"),
    (r"đánh giá", "quá ít bằng chứng là điểm đáng gợi ý"),
)
# v1 `plan_tier_reason` was written without diacritics.
PLAN_TIER_REASON_VI = {
    "nam trong Ngu Hanh Son, da tinh trong diem do": "nằm trong Ngũ Hành Sơn, đã tính trong điểm đó",
    "co so y te hoac tham my, khong phai diem du lich": "cơ sở y tế hoặc thẩm mỹ, không phải điểm du lịch",
    "nha tho toc, khong phai diem tham quan": "nhà thờ tộc, không phải điểm tham quan",
    "chi mo theo doan, phai lien he truoc": "chỉ mở theo đoàn, phải liên hệ trước",
    "khu an uong trong Cho Con, khong phai cho": "khu ăn uống trong Chợ Cồn, không phải chợ",
    "vuon tu nhan, phai lien he truoc": "vườn tư nhân, phải liên hệ trước",
    "lop hoc, chi xep khi duoc hoi": "lớp học, chỉ xếp khi được hỏi",
    "mua qua la viec khach chon, khong phai diem cua moi ngay":
        "mua quà là việc khách chọn, không phải điểm của mọi ngày",
    "hoat dong rieng": "hoạt động riêng",
    "di ca ngay": "đi cả ngày",
    "chua co danh gia": "ít thông tin về điểm, chỉ xếp khi được hỏi",
    "khu vui choi tre em": "khu vui chơi trẻ em",
    "theo goi doan": "theo gói đoàn",
}
# Coarse `tags.good_times` windows (minutes), used to keep the tag
# consistent with SOURCED opening hours.
GOOD_TIME_SPANS = {"sunrise": [(300, 420)], "morning": [(420, 660)],
                   "sunset": [(990, 1110)], "night": [(1110, 1380)]}


# --------------------------------------------------------------------------
# io
# --------------------------------------------------------------------------

def _load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        if path.endswith(".jsonl"):
            return [json.loads(x) for x in f if x.strip()]
        return json.load(f)


def _dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def _csv(path, rows, cols):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


def prov(source, verified_by, evidence_url=None, note=None, confidence=None,
         verified_at=None):
    assert verified_by in VERIFIED_BY, verified_by
    c = CONF[verified_by] if confidence is None else confidence
    return {"source": source, "verified_by": verified_by,
            "confidence": round(float(c), 2), "evidence_url": evidence_url,
            "verified_at": verified_at, "note": note}


def _spans_list(spans) -> list[str]:
    return R.fmt(spans)[0].split(", ") if spans else []


def _int(v):
    return None if v is None else int(round(float(v)))


def tier_of_range(lo, hi) -> str | None:
    """`price.tier` from a VND range: free when nothing is paid, else the
    tier of the midpoint (or of the only known end)."""
    if lo is None and hi is None:
        return None
    if (hi if hi is not None else lo) <= 0:
        return "free"
    mid = (lo + hi) / 2 if lo is not None and hi is not None else (lo if lo is not None else hi)
    return R.tier_of_vnd(mid)


# --------------------------------------------------------------------------
# per-field builders
# --------------------------------------------------------------------------

def osm_name_ok(name, osm, max_m=60, min_ratio=0.6):
    """An OSM element counts as the same place only if it is close AND its
    name matches (v1 `osm_evidence` was joined by distance alone)."""
    dist = osm.get("dist_m")
    if dist is None or dist > max_m or not osm.get("name"):
        return False
    a, b = R.fold(name), R.fold(osm["name"])
    if not a or not b:
        return False
    return a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= min_ratio


def _osm_ref(raw: str | None) -> str | None:
    """'n123' / 'node/123' / 'osm:node/123' -> 'node/123'."""
    if not raw:
        return None
    raw = raw[4:] if raw.startswith("osm:") else raw
    m = re.fullmatch(r"([nwr])(\d+)", raw)
    if m:
        return {"n": "node", "w": "way", "r": "relation"}[m.group(1)] + "/" + m.group(2)
    return raw if re.fullmatch(r"(node|way|relation)/\d+", raw) else None


_NAME_NOISE = {"da", "nang", "danang", "hoi", "an", "restaurant", "nha", "hang", "quan",
               "bar", "pub", "seafood", "hai", "san", "spa", "massage", "cafe", "coffee",
               "ca", "phe", "the", "and", "va"}


def osm_names_agree(name: str, tags: dict) -> bool:
    """Same place by name? Generic words (city, 'coffee', 'nhà hàng'...) are
    dropped first: 'H Coffee' and 'Alo Coffee' 67 m apart are two shops."""
    def key(n):
        return " ".join(w for w in R.fold(n).split() if w not in _NAME_NOISE)
    a = key(name)
    for k in ("name", "name:vi", "name:en", "matched_name"):
        b = key(tags.get(k) or "")
        if a and b and (a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= 0.5):
            return True
    return False


def osm_link(p, ctx):
    """(osm element, dist_m, tags, how) for one POI, best evidence first:
    the POI's own OSM id, a fresh Overpass match, main's OSM cross-check, the
    v1 `osm_evidence`. A match only counts when the names agree."""
    pid = p["poi_id"]
    ev = p.get("osm_evidence") or {}
    om = ctx["osm_match"].get(pid)
    if p.get("source") == "osm/overpass":
        own = _osm_ref(pid)
        tags = dict(om.get("tags") or {}) if om and _osm_ref(om["osm"]) == own else {}
        tags.setdefault("opening_hours", ev.get("hours"))
        return own, 0.0, tags, "own_id"
    if om and osm_names_agree(p["name"], om.get("tags") or {}):
        return _osm_ref(om["osm"]), om.get("dist_m"), om.get("tags") or {}, "overpass_match"
    xm = (ctx["osm_x"].get(pid) or {}).get("match")
    if xm and (xm.get("score") or 0) >= 0.6 and (xm.get("dist_m") or 1e9) <= 120 \
            and osm_names_agree(p["name"], {**(xm.get("tags") or {}), "matched_name": xm.get("matched_name"),
                                            "name": xm.get("name")}):
        return _osm_ref(xm.get("osm")), xm.get("dist_m"), xm.get("tags") or {}, "osm_crosscheck"
    if ev.get("osm") and osm_name_ok(p["name"], ev) and osm_names_agree(p["name"], ev):
        return _osm_ref(ev["osm"]), ev.get("dist_m"), {"opening_hours": ev.get("hours")}, "v1_evidence"
    return None, None, {}, None


def build_hours(p, archetype, ctx, osm_tags, web_item):
    """-> (hours, provenance, quarantine part)."""
    arch = R.ARCHETYPES[archetype]
    raw = list(p.get("opening_hours") or [])
    src = p.get("hours_source") or ""
    google = src in GOOGLE_HOURS_SOURCES or (p.get("source") == GOOGLE_SOURCE and not src)
    every = R.intersect_all(raw)
    q = {}
    if google and raw:
        q["opening_hours"] = raw
        if p.get("hours_by_day"):
            q["hours_by_day"] = p["hours_by_day"]

    chosen, pv, closed = None, None, []
    hw = ctx["hours_web"].get(p["name"]) or {}
    wi = web_item or {}
    wi_spans = R.parse_element(wi.get("hours") or "")
    osm_week = R.parse_osm_hours(osm_tags.get("opening_hours"))
    if src == "user-verify" and every:
        chosen, pv = every, prov("user_review", "user", note=p.get("hours_note"))
    elif wi_spans:
        # `hours_*` keys: a web row that only adds hours keeps its own proof,
        # apart from the price note / URL of an older row for the same POI.
        chosen = wi_spans
        pv = prov("web", "agent_web", evidence_url=wi.get("hours_evidence_url") or wi.get("evidence_url"),
                  note=wi.get("hours_note") or wi.get("note"),
                  verified_at=wi.get("hours_checked_at") or wi.get("checked_at"),
                  confidence=wi.get("hours_confidence", wi.get("confidence", 0.6)))
    elif src == "web" and every:
        url = next(iter(hw.get("price_sources") or p.get("price_sources") or []), None)
        note = hw.get("hours_web") or (p.get("web_evidence") or {}).get("hours_web")
        chosen = every
        pv = prov("web", "agent_web", evidence_url=url, note=note, confidence=0.6 if url else 0.5)
    elif src == "osm-converted" and every:
        chosen, pv = every, prov("osm", "open_data", note="giờ OSM (v1)")
    elif p.get("source") == "osm/overpass" and every and not google:
        chosen, pv = every, prov("osm", "open_data", note="giờ OSM (v1)")
    elif osm_week is not None:
        wi = R.week_intersection(osm_week)
        note = f"OSM opening_hours='{osm_tags.get('opening_hours')}'"
        if not wi:
            wi, closed = R.open_days_intersection(osm_week)
            if wi and closed:
                note += f"; đóng cửa {','.join(closed)}"
        if wi:
            chosen = wi
            pv = prov("osm", "open_data", note=note, confidence=0.65)
        else:
            closed = []
    if chosen is None and src in OPEN_SPACE_HOURS and every:
        chosen, pv = every, prov("rule_open_access", "inferred", confidence=0.55,
                                 note="không gian mở, không cổng")
    elif chosen is None and src == "rule_temple_default" and every:
        chosen, pv = every, prov("rule_temple_default", "inferred",
                                 note="giờ mặc định của chùa (v1)")
    if chosen is None:
        safe = [s for w in arch["safe"] for s in R.parse_element(w)]
        if safe:
            chosen = safe
            pv = prov(f"archetype:{archetype}", "inferred",
                      note="khung an toàn theo nhóm giờ — nên kiểm tra giờ thật")
        else:
            pv = prov("none", "inferred", confidence=0.0,
                      note="KHÔNG XÁC ĐỊNH — cần tra trang chính thức")

    access = None
    on_peninsula = p["lat"] >= 16.095 and p["lon"] >= 108.245
    if "07:30-18:30" in (p.get("access_note") or "") and on_peninsula:
        # Sơn Trà peninsula road window; Oct-Feb is 07:30-17:30. Use the
        # stricter one all year (conservative; source in access_note).
        access = R.parse_element("07:30-17:30")
    final = R.intersect(chosen, access) if (chosen and access) else (chosen or [])
    open_ = _spans_list(final)
    kind = "unknown" if not open_ else (
        "fixed" if pv["verified_by"] in FIXED_HOURS_BY else "safe_window")
    hours = {"open": open_, "kind": kind, "closed_days": closed,
             "access_window": _spans_list(access) or None, "archetype": archetype}
    return hours, pv, q


def build_price(p, category, archetype, ctx, web_item, parent, in_paid_cluster):
    """-> (price, provenance, quarantine part). VND per person per visit."""
    q = {}
    st = p.get("smart_tags") or {}
    if p.get("source") == GOOGLE_SOURCE and p.get("price_note") \
            and not str(p["price_note"]).startswith("user:"):
        q["price_note"] = p["price_note"]
        g = R.parse_google_price(p["price_note"])
        if g:
            q["price_range"] = {k: _int(v) for k, v in g.items()}
    if st.get("price_band") and (p.get("source") == GOOGLE_SOURCE or st.get("band_verified")):
        q["price_band_v1"] = st["price_band"]      # read off Google Maps (v1 review)

    def out(lo, hi, note=None):
        lo, hi = _int(lo), _int(hi)
        if lo is not None and hi is not None and hi < lo:
            hi = lo
        return {"tier": tier_of_range(lo, hi), "min_vnd": lo, "max_vnd": hi, "note": note}

    if category == "lodging":
        return {"tier": None, "min_vnd": None, "max_vnd": None, "note": None}, \
            prov("n/a", "inferred", confidence=0.0,
                 note="lưu trú là điểm xuất phát, không tính chi tiêu/lượt"), q
    if parent and R.ROLE_OF[category] == "attraction":
        return {"tier": "included", "min_vnd": 0, "max_vnd": 0, "note": None}, \
            prov("cluster_rule", "inferred", confidence=0.6, note=f"vé tính ở {parent['name']}"), q

    name = p["name"]
    pw = ctx["price_web"].get(name) or {}
    urls = list(pw.get("price_sources") or p.get("price_sources") or [])
    ticket_note = p.get("ticket_note") or pw.get("ticket_note")
    wi = web_item or {}
    if wi.get("ticket_vnd") is not None or wi.get("free_entry") or wi.get("min_vnd") is not None:
        tv = wi.get("ticket_vnd")
        lo, hi = wi.get("min_vnd", tv), wi.get("max_vnd", tv)
        if wi.get("free_entry"):
            lo = hi = 0
        note = wi.get("note") or ticket_note
        if wi.get("_via_alt_group"):
            note = f"[giá chung nhóm {wi['_via_alt_group']}] " + (wi.get("note") or "")
        conf = (wi.get("confidence", 0.6) if wi.get("evidence_url") else 0.5) - \
            (0.05 if wi.get("_via_alt_group") else 0)
        return out(lo, hi, note), prov("web", "agent_web", evidence_url=wi.get("evidence_url"),
                                       note=note, verified_at=wi.get("checked_at"),
                                       confidence=conf), q
    if p.get("ticket_vnd") is not None:
        tv = int(p["ticket_vnd"])
        is_user = "user" in (ticket_note or "")
        return out(tv, tv, ticket_note), prov(
            "user_review" if is_user else "web", "user" if is_user else "agent_web",
            evidence_url=urls[0] if urls else None, note=ticket_note,
            confidence=0.7 if is_user else (0.6 if urls else 0.5)), q
    note = str(p.get("price_note") or "")
    if note.startswith("user:"):
        rng = R.parse_user_price(note)
        if rng:
            hi = rng.get("max") if rng.get("max") is not None else rng.get("min")
            return out(rng.get("min"), hi, note), prov("user_review", "user", note=note), q
    if pw.get("price_band") in R.TIER_BOUNDS and urls:
        lo, hi = R.TIER_BOUNDS[pw["price_band"]]
        return out(lo, hi, ticket_note), prov(
            "web", "agent_web", evidence_url=urls[0], confidence=0.55,
            note="web chỉ cho mức giá, khoảng = khoảng của mức"), q
    if category in R.FREE_PUBLIC and not st.get("ticket") and not in_paid_cluster:
        return out(0, 0), prov("rule_free_public", "inferred", confidence=0.7,
                               note="nơi công cộng (biển/chùa/công viên/điểm ngắm) — vào cửa tự do"), q
    if category == "restaurant":
        f = R.fold(name) + " " + R.fold(p.get("type"))
        rng = dict(R.RESTAURANT_PRICE.get(archetype, R.RESTAURANT_PRICE["nha_hang"]))
        if R._has(f, R.HIGH_END_KEYS):
            rng = {"min": 200_000, "max": 600_000}
        return out(rng["min"], rng["max"]), prov(
            f"category_default:{archetype}", "inferred", confidence=0.4,
            note="ƯỚC LƯỢNG theo kiểu quán"), q
    if category == "paid_attraction" and R._has(R.fold(name), ("cooking", "class", "workshop")):
        return out(750_000, 1_100_000), prov(
            "category_default:cooking_class", "inferred", confidence=0.45,
            note="ƯỚC LƯỢNG: lớp nấu ăn Đà Nẵng US$29-40/người (cookly/pelago 11/2026)"), q
    if category in R.CATEGORY_PRICE:
        rng = R.CATEGORY_PRICE[category]
        return out(rng["min"], rng["max"]), prov(
            f"category_default:{category}", "inferred", confidence=0.4,
            note="ƯỚC LƯỢNG theo thể loại"), q
    return {"tier": None, "min_vnd": None, "max_vnd": None, "note": ticket_note}, prov(
        "none", "inferred", confidence=0.0,
        note="KHÔNG XÁC ĐỊNH — giá vé phải tra trang chính thức (không đoán)"), q


def build_dwell(p, kind):
    """-> (dwell, provenance, quarantine part). Minutes on site."""
    src = p.get("dur_source")
    vm = p.get("visit_min") or {}
    q = {}
    if src == "google_typical":
        q["visit_min"] = vm
    if src == "human" and vm:
        return {k: int(vm[k]) for k in ("p25", "p50", "p75")}, prov(
            "user_review", "user", note=p.get("dur_note")), q
    if src == "curated" and vm:
        return {k: int(vm[k]) for k in ("p25", "p50", "p75")}, prov(
            "curated_v1", "inferred", confidence=0.55,
            note="chọn tay theo hiểu biết chung về điểm (v1), không phải đo"), q
    q25, q50, q75 = R.DWELL[kind]
    return {"p25": q25, "p50": q50, "p75": q75}, prov(
        f"dwell_table_v2:{kind}", "inferred", confidence=0.4,
        note="ƯỚC LƯỢNG theo loại điểm; hiệu chỉnh lại từ log pilot"), q


def category_defaults(v1_pois, cats):
    """Clean tag priors per category, read off the v1 POIs of the same
    category (mode for labels, median for numbers). New POIs from open data
    get these, labelled as category defaults."""
    acc = defaultdict(lambda: defaultdict(list))
    for p in v1_pois:
        st = p.get("smart_tags") or {}
        a = acc[cats[p["poi_id"]]]
        for k in ("sun_exposure", "outdoor_exposure"):
            if isinstance(st.get(k), (int, float)):
                a[k].append(float(st[k]))
        if st.get("rain_cover") in RAIN_COVERS:
            a["rain_cover"].append(st["rain_cover"])
        if st.get("space") in ("indoor", "outdoor"):
            a["indoor"].append(st["space"] == "indoor")
        if st.get("party"):
            a["party"].append(tuple(sorted(st["party"])))
        if st.get("time"):
            a["good_times"].append(tuple(st["time"]))
    out = {}
    for cat, a in acc.items():
        def mode(k, default=None):
            return Counter(a[k]).most_common(1)[0][0] if a[k] else default

        def median(k):
            return round(statistics.median(a[k]), 2) if a[k] else None
        out[cat] = {"sun_exposure": median("sun_exposure"),
                    "outdoor_exposure": median("outdoor_exposure"),
                    "rain_cover": mode("rain_cover"), "indoor": mode("indoor"),
                    "party": list(mode("party", ())), "good_times": list(mode("good_times", ()))}
    return out


def build_tags(p, category, kind, dwell, defaults, is_new):
    """-> (tags, provenance)."""
    st = p.get("smart_tags") or {}
    d = defaults.get(category, {})
    used_default = []

    def pick(key, value):
        if value is None or value == []:
            if d.get(key) not in (None, []):
                used_default.append(key)
            return d.get(key)
        return value

    space = st.get("space")
    indoor = {"indoor": True, "outdoor": False}.get(space)
    if indoor is None and space not in ("both", "unknown"):
        indoor = pick("indoor", None)
    party = [x for x in PARTIES if x in (pick("party", list(st.get("party") or [])) or [])]
    good = [] if category == "lodging" else \
        [t for t in GOOD_TIMES if t in (pick("good_times", list(st.get("time") or [])) or [])]
    if category == "lodging":
        used_default.clear()
    # One concept, one source: the time budget is the size of the visit, so
    # it follows `dwell` (the v1 `budget` tag contradicted it for 139 POIs,
    # e.g. a 30-minute viewpoint tagged "full-day").
    time_budget = time_budget_of(dwell["p50"])
    tier = p.get("plan_tier")
    on_request = (tier == "wish_only" and p.get("plan_tier_reason") != OUT_OF_SCOPE_REASON) \
        if tier else kind in ON_REQUEST_KINDS
    reason = plan_tier_reason(p)
    effort = p.get("intensity") if isinstance(p.get("intensity"), int) else EFFORT_BY_KIND.get(kind, 1)
    sun = st.get("sun_exposure") if isinstance(st.get("sun_exposure"), (int, float)) else None
    out_e = st.get("outdoor_exposure") if isinstance(st.get("outdoor_exposure"), (int, float)) else None
    rain = st.get("rain_cover") if st.get("rain_cover") in RAIN_COVERS else None
    sun, out_e, rain = pick("sun_exposure", sun), pick("outdoor_exposure", out_e), pick("rain_cover", rain)
    ws = p.get("weather_sensitive") if isinstance(p.get("weather_sensitive"), bool) else None
    if ws is None:
        ws = bool(out_e is not None and out_e >= 0.55)
    tags = {
        "indoor": indoor, "effort": int(effort),
        "kid_friendly": "family" in party and category != "nightlife",
        "party": party, "good_times": good, "time_budget": time_budget,
        "on_request": bool(on_request),
        "sun_exposure": sun, "outdoor_exposure": out_e, "rain_cover": rain,
        "weather_sensitive": bool(ws),
    }
    note = []
    if on_request:
        note.append(f"on_request: {reason}" if tier == "wish_only" else f"on_request: loại {kind}")
    if used_default:
        note.append("mặc định theo thể loại: " + ",".join(sorted(set(used_default))))
    src = "category_defaults" if is_new else (p.get("smart_tag_source") or "smart_tags_v1")
    return tags, prov(src, "inferred", confidence=0.4 if is_new else 0.5,
                      note="; ".join(note) or None)


def prize_prior(category, signature, audience, wikidata, sitelinks, views):
    """`popularity.prize_prior` in [0,1] + (verified_by, confidence, note).

    Clean signals only (DATA_SPEC.md section 3): category prior, approved
    signature list, Wikidata presence/sitelinks, Wikipedia 90-day views
    (log-scaled); a `local` audience lowers it. Google rating is NOT an input.
    """
    p = CATEGORY_PRIOR.get(category, 0.4)
    parts = [f"category={p}"]
    if wikidata:
        p += 0.1
        parts.append("wikidata")
    if sitelinks:
        p += 0.15 * min(1.0, math.log1p(sitelinks) / math.log1p(60))
        parts.append(f"sitelinks={sitelinks}")
    if views:
        p += 0.15 * min(1.0, math.log1p(views) / math.log1p(200_000))
        parts.append(f"views90d={views}")
    if signature:
        p = max(p, 0.9) + (0.05 if (sitelinks or views) else 0.0)
        parts.append("signature")
    elif audience == "local":
        p = max(0.05, p - LOCAL_PENALTY)
        parts.append("audience=local")
    p = round(min(1.0, p), 3)
    rich = bool(sitelinks or views)
    return p, ("open_data" if rich else "inferred"), (0.6 if rich else 0.4), "; ".join(parts)


def clean_reason(note: str) -> str:
    """v1 review note -> short reason without Google numbers."""
    for pat, reason in REASON_RULES:
        m = re.search(pat, note)
        if m:
            name = next((g.strip() for g in m.groups() if g), None)
            return reason.format(name) if "{}" in reason else reason
    return "loại khi duyệt v1"


def plan_tier_reason(p) -> str | None:
    r = p.get("plan_tier_reason")
    return PLAN_TIER_REASON_VI.get(r, r)


def inherit_parent_hours(recs):
    """A stop inside a ticketed area (`requires_ticket_of`) can only be
    visited while the parent's gate is open: its hours are cut to the
    parent's hours, which become its `access_window`."""
    by_id = {r["poi_id"]: r for r in recs}
    for r in recs:
        parent = by_id.get(r["requires_ticket_of"] or "")
        if not parent or not parent["hours"]["open"]:
            continue
        gate = [s for w in parent["hours"]["open"] for s in R.parse_element(w)]
        own = [s for w in r["hours"]["open"] for s in R.parse_element(w)]
        if not own:
            # no hours of its own: visitable while the gate is open
            r["hours"].update(open=_spans_list(gate), kind="safe_window",
                              access_window=_spans_list(gate))
            r["provenance"]["hours"] = prov("parent_gate", "inferred", confidence=0.5,
                                            note=f"giờ cổng {parent['name']}; giờ riêng chưa có nguồn")
            continue
        cut = R.intersect(own, gate)
        if not cut:
            continue
        r["hours"]["open"] = _spans_list(cut)
        r["hours"]["access_window"] = _spans_list(gate)
        pv = r["provenance"]["hours"]
        pv["note"] = "; ".join(x for x in (pv["note"], f"cắt theo giờ cổng {parent['name']}") if x)


# Hour groups a POI may switch to when its Google hours (quarantined) contradict
# the group the name rules gave it (e.g. a breakfast-only mì Quảng shop typed
# as a lunch place). Only the GROUP changes; its window is still our table's.
FIT_FAMILY = {
    "restaurant": ("an_sang", "com_trua", "nha_hang", "an_toi"),
    "cafe": ("cafe", "an_sang", "com_trua"),
    "nightlife": ("bar", "an_toi", "com_trua", "cafe"),
    "wellness": ("spa",),
    "day_market": ("cho_ngay", "cua_hang", "cho_dem"),
    "night_market": ("cho_dem",),
    "religious": ("chua",),
    "museum_indoor": ("bao_tang",),
    "beach": ("ngoai_troi_do_thi", "ngoai_troi_tu_nhien"),
    "viewpoint": ("ngoai_troi_tu_nhien", "ngoai_troi_do_thi", "cho_dem"),
    "outdoor_landmark": ("ngoai_troi_do_thi", "ngoai_troi_tu_nhien", "bao_tang"),
    "paid_attraction": ("co_ve", "su_kien_toi"),
}
FIT_TRIGGER = 0.5     # refit when less than half of the window is inside Google hours
FIT_MIN = 0.85        # accept a group when >= 85 % of its window is inside (calibration level)


def _minutes(spans) -> int:
    return sum(b - a for a, b in spans)


def inside_share(open_, google) -> float | None:
    """Share of our window `open_` that lies inside the every-day Google hours."""
    mine = [s for w in open_ for s in R.parse_element(w)]
    g = R.intersect_all(google)
    if not mine or not g:
        return None
    return _minutes(R.intersect(mine, g) or []) / _minutes(mine)


def fit_archetype(p, cat, arch, hours, google, build):
    """-> (archetype, conflict). `build(a)` rebuilds the hours with group `a`.
    An empty window (e.g. bar hours cut away by the Sơn Trà road window)
    counts as 0 % inside, so it is refitted too."""
    if not R.intersect_all(google):
        return arch, False
    share = inside_share(hours["open"], google) if hours["open"] else 0.0
    if share >= FIT_TRIGGER:
        return arch, False
    best = (share, _minutes([s for w in hours["open"] for s in R.parse_element(w)]), arch)
    for a in FIT_FAMILY.get(cat, ()):
        if a == arch:
            continue
        h = build(a)
        if h["kind"] != "safe_window":
            continue
        s = inside_share(h["open"], google)
        if s is not None and (s, _minutes([x for w in h["open"] for x in R.parse_element(w)])) > best[:2]:
            best = (s, _minutes([x for w in h["open"] for x in R.parse_element(w)]), a)
    return (best[2], False) if best[0] >= FIT_MIN else (arch, True)


_NOTE_REVIEWS = re.compile(r"[\d,]+★,\s*([\d.]+)\s*đánh giá")


def v1_review_note(p) -> str:
    return " | ".join(b.get("note") or "" for b in ((p.get("review") or {}).get("by") or []))


def review_count_of_note(note: str) -> int | None:
    """'Còn trên Google (4,8★, 3207 đánh giá)' -> 3207 (Google content: quarantine only)."""
    m = _NOTE_REVIEWS.search(note or "")
    return int(m.group(1).replace(".", "")) if m else None


def reconcile(rec):
    """Cross-field consistency after rules and user decisions: a good-time
    tag must overlap SOURCED opening hours (inferred safe windows are a
    conservative subset of the real hours, so they do not prune tags)."""
    if rec["hours"]["kind"] != "fixed" or not rec["tags"]["good_times"]:
        return
    spans = [s for w in rec["hours"]["open"] for s in R.parse_element(w)]
    keep = [g for g in rec["tags"]["good_times"] if R.intersect(spans, GOOD_TIME_SPANS[g])]
    if keep != rec["tags"]["good_times"]:
        dropped = [g for g in rec["tags"]["good_times"] if g not in keep]
        rec["tags"]["good_times"] = keep
        pv = rec["provenance"]["tags"]
        pv["note"] = "; ".join(x for x in (pv["note"], f"bỏ good_times {','.join(dropped)} "
                                           "(ngoài giờ mở có nguồn)") if x)


def build_status(p, category, pid):
    """-> (status, reason, provenance, quarantine part)."""
    q = {}
    review = p.get("review") or {}
    by = review.get("by") or []
    notes = " | ".join(b["note"] for b in by if b.get("note"))
    when = next((b["ts"][:10] for b in by if b.get("ts")), None)
    if category == "lodging":
        return "active", None, prov("rules_v2", "inferred",
                                    note="lưu trú = điểm xuất phát (role base)"), q
    excl = R.exclusion_reason(p["name"], p.get("type"))
    if excl:
        return "excluded", excl, prov("rules_v2", "inferred", confidence=0.6), q
    if review.get("verdict") == "loai":
        if notes:
            q["review_note_v1"] = notes
        return "excluded", clean_reason(notes), prov(
            "review_v1", "inferred", confidence=0.6, verified_at=when,
            note="duyệt v1 (claude-google-maps); ghi chú gốc trong quarantine"), q
    if p.get("plan_tier") == "excluded":
        return "excluded", plan_tier_reason(p) or "không xếp vào lịch (v1)", prov(
            "plan_tier_v1", "inferred", confidence=0.6), q
    rev = R.review_reason(p["name"], category, pid, p.get("type"))
    if rev:
        return "review", rev, prov("rules_v2", "inferred", confidence=0.5), q
    if review.get("verdict") == "dung":
        return "active", None, prov("review_v1", "inferred", confidence=0.6, verified_at=when), q
    return "active", None, prov("rules_v2", "inferred", confidence=0.5), q


# --------------------------------------------------------------------------
# clusters, duplicates, new POIs
# --------------------------------------------------------------------------

def find_clusters(pois, cats):
    by_name = {p["name"]: p for p in pois}
    cluster, parent_of, alt = {}, {}, {}
    for cid, (parent, anchor, radius) in CLUSTERS.items():
        if parent not in by_name or anchor not in by_name:
            continue
        a = by_name[anchor]
        for p in pois:
            if cats[p["poi_id"]] == "lodging":
                continue
            if R.haversine_m(a["lat"], a["lon"], p["lat"], p["lon"]) > radius:
                continue
            role = R.ROLE_OF[cats[p["poi_id"]]]
            if cid == "bay_mau":
                if not any(k in R.fold(p["name"]) for k in ("dua", "thuyen thung", "basket")):
                    continue
                alt[p["poi_id"]] = "bay_mau"
            if role != "attraction" and cid != "ba_na":
                continue
            cluster[p["poi_id"]] = cid
            if cid == "ba_na" and p["name"] != parent:
                parent_of[p["poi_id"]] = by_name[parent]
            if cid == "ngu_hanh_son" and p["name"] in NHS_TICKETED:
                parent_of[p["poi_id"]] = by_name[parent]
    if "Ba Na Hills" in by_name and "Sun World Bà Nà Hills" in by_name:
        alt[by_name["Ba Na Hills"]["poi_id"]] = "ba_na_entry"
        alt[by_name["Sun World Bà Nà Hills"]["poi_id"]] = "ba_na_entry"
    return cluster, parent_of, alt


_GENERIC = {"chua", "nha", "tho", "giao", "xu", "bai", "bien", "tam", "quan",
            "ca", "phe", "cafe", "coffee", "nha hang", "da", "nang", "spa", "cho",
            "beach", "the", "va", "and", "dong", "hotel", "khach", "san"}


def find_duplicates(pois, max_m=150, min_ratio=0.72):
    def key(n):
        return " ".join(w for w in R.fold(n).split() if w not in _GENERIC)

    out = []
    for i in range(len(pois)):
        a = pois[i]
        for j in range(i + 1, len(pois)):
            b = pois[j]
            same = R.fold(a["name"]) == R.fold(b["name"])
            lim = 1500 if same else max_m
            if abs(a["lat"] - b["lat"]) > lim / 1e5 or abs(a["lon"] - b["lon"]) > lim / 1e5:
                continue
            d = R.haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
            if d > lim:
                continue
            ka, kb = key(a["name"]), key(b["name"])
            r = difflib.SequenceMatcher(None, ka, kb).ratio() if ka and kb else 0.0
            if same or r >= min_ratio:
                out.append({"a_id": a["poi_id"], "a_name": a["name"], "b_id": b["poi_id"],
                            "b_name": b["name"], "dist_m": round(d, 1), "name_ratio": round(r, 2)})
    return out


def load_new_pois(sources_dir, existing):
    """POIs from `new_pois_*.json` (OpenStreetMap, ODbL) -> (v1-shaped
    records, curated category, old-town ticket ids, price rows, skipped)."""
    new, cats, old_town, prices, skipped = [], {}, set(), [], []
    if not os.path.isdir(sources_dir):
        return new, cats, old_town, prices, skipped
    have = {p["poi_id"] for p in existing}
    for fn in sorted(os.listdir(sources_dir)):
        if not (fn.startswith("new_pois_") and fn.endswith(".json")):
            continue
        doc = _load(os.path.join(sources_dir, fn), {})
        cur = doc.get("curation", {})
        disp = cur.get("display_name", {})
        for it in doc.get("items", []):
            pid = f"osm:{it['osm']}"
            if pid in have:
                continue
            name = disp.get(it["osm"], it["name"])
            dup = next((q for q in existing
                        if abs(q["lat"] - it["lat"]) <= 0.001 and abs(q["lon"] - it["lon"]) <= 0.001
                        and R.haversine_m(q["lat"], q["lon"], it["lat"], it["lon"]) <= 100
                        and osm_name_ok(q["name"], {"name": name, "dist_m": 0}, min_ratio=0.7)), None)
            if dup:
                skipped.append({"new": pid, "name": name, "existing": dup["poi_id"],
                                "existing_name": dup["name"], "lat": it["lat"], "lon": it["lon"],
                                "category": cur.get("category", {}).get(it["osm"])
                                or OSM_CAT.get(it.get("c"), "outdoor_landmark")})
                continue
            new.append({
                "poi_id": pid, "name": name, "name_osm": it["name"], "name_en": it.get("en"),
                "lat": it["lat"], "lon": it["lon"], "source": "osm/overpass",
                "opening_hours": [], "hours_source": "", "wikidata": it.get("wd"),
                "_new_file": fn,
                "osm_evidence": {"osm": it["osm"], "dist_m": 0.0, "hours": it.get("oh"),
                                 "fee": it.get("fee"), "name": name},
            })
            have.add(pid)
            cats[pid] = cur.get("category", {}).get(it["osm"]) or OSM_CAT.get(it.get("c"), "outdoor_landmark")
        old_town |= {f"osm:{x}" for x in cur.get("old_town_ticket", [])}
        for row in doc.get("prices", []):
            prices.append({**row, "checked_at": doc.get("fetched_at")})
    return new, cats, old_town, prices, skipped


# --------------------------------------------------------------------------
# user decisions (always win)
# --------------------------------------------------------------------------

def load_decisions(sources_dir):
    """{poi_id: {name?, status?, status_reason?, category?, requires_ticket_of?}}
    from BE/data/sources/decisions_*.json (later files override earlier)."""
    out = {}
    if os.path.isdir(sources_dir):
        for fn in sorted(os.listdir(sources_dir)):
            if fn.startswith("decisions_") and fn.endswith(".json"):
                for pid, d in (_load(os.path.join(sources_dir, fn), {}) or {}).get("items", {}).items():
                    out.setdefault(pid, {}).update({**d, "_file": fn})
    return out


def load_human_verify(sources_dir):
    """{poi_id: item} from BE/data/sources/human_verify_v2_*.json."""
    out = {}
    if os.path.isdir(sources_dir):
        for fn in sorted(os.listdir(sources_dir)):
            if fn.startswith("human_verify_v2_") and fn.endswith(".json"):
                for it in (_load(os.path.join(sources_dir, fn), {}) or {}).get("items", []):
                    out[it["poi_id"]] = {**it, "_file": fn}
    return out


def apply_decision(rec, d):
    """User decision (names, review, duplicates, old-town ticket) -> record."""
    pv = rec["provenance"]
    if d.get("name"):
        rec["name"] = d["name"]
        pv["name"] = prov("user_decision", "user", note=f"{d['_file']}; tên gốc trong name_raw")
    if d.get("status") in ("active", "review", "excluded"):
        rec["status"] = d["status"]
        rec["status_reason"] = d.get("status_reason") if d["status"] != "active" else None
        pv["status"] = prov("user_decision", "user", note=d["_file"])
    if d.get("category") in R.ALL_CATEGORIES:
        rec["category"], rec["role"] = d["category"], R.ROLE_OF[d["category"]]
        pv["category"] = prov("user_decision", "user", note=d["_file"])
    if "requires_ticket_of" in d:
        parent = d["requires_ticket_of"]
        rec["requires_ticket_of"] = parent
        if parent and rec["role"] == "attraction":
            rec["price"].update(tier="included", min_vnd=0, max_vnd=0)
            pv["price"] = prov("user_decision", "user", note=f"{d['_file']}; vé tính ở {parent}")
        elif not parent and rec["price"]["tier"] == "included":
            rec["price"].update(tier=None, min_vnd=None, max_vnd=None)
            pv["price"] = prov("user_decision", "user", confidence=0.0,
                               note=f"{d['_file']}; bỏ khỏi vé chung — giá chưa biết")


def apply_human_verify(rec, it):
    """Human-checked hours/price. `human` needs an evidence URL, otherwise
    the value is recorded as `user` (DATA_SPEC.md verified_by)."""
    url = it.get("evidence_url")
    by = "human" if url else "user"
    when = it.get("checked_at") or TODAY
    if it.get("hours"):
        spans = [s.strip() for s in str(it["hours"]).split(",") if s.strip()]
        if spans and all(R.parse_span(s) for s in spans):
            rec["hours"]["open"], rec["hours"]["kind"] = spans, "fixed"
            rec["provenance"]["hours"] = prov("human_verify", by, evidence_url=url,
                                              verified_at=when, note=it["_file"])
    vnd = it.get("ticket_vnd")
    tier = it.get("price_tier")
    if tier is None and vnd is not None:
        tier = R.tier_of_vnd(vnd)
    if tier in R.PRICE_TIERS and not (tier == "included") ^ bool(rec["requires_ticket_of"]):
        if vnd is not None and tier != "included":
            rec["price"].update(min_vnd=int(vnd), max_vnd=int(vnd), tier=tier_of_range(vnd, vnd))
        elif tier in ("free", "included"):
            rec["price"].update(tier=tier, min_vnd=0, max_vnd=0)
        else:
            lo, hi = R.TIER_BOUNDS[tier]
            rec["price"].update(tier=tier, min_vnd=lo, max_vnd=hi)
        note = it["_file"] + (f"; VND {vnd}" if vnd is not None else "")
        rec["provenance"]["price"] = prov("human_verify", by, evidence_url=url,
                                          verified_at=when, note=note)


# --------------------------------------------------------------------------
# main build
# --------------------------------------------------------------------------

def load_context(v1_dir, sources_dir):
    ctx = {
        "hours_web": _load(os.path.join(v1_dir, "hours_web.json"), {}) or {},
        "price_web": _load(os.path.join(v1_dir, "price_web.json"), {}) or {},
        "osm_x": (_load(os.path.join(v1_dir, "osm_crosscheck.json"), {}) or {}).get("pois", {}),
        "osm_match": (_load(os.path.join(sources_dir, "osm_match.json"), {}) or {}).get("items", {}),
        "popularity": _load(os.path.join(sources_dir, "popularity.json"), {}) or {},
        "web": {}, "gcheck": {}, "files": [],
    }
    for fn in sorted(os.listdir(sources_dir)) if os.path.isdir(sources_dir) else []:
        if fn.endswith(".json") and not fn.startswith("osm_gap"):
            ctx["files"].append(fn)
        if fn.startswith("agent_web_") and fn.endswith(".json"):
            doc = _load(os.path.join(sources_dir, fn), {})
            for row in doc.get("items", []):
                row = dict(row)
                stamp = "hours_checked_at" if any(k.startswith("hours_") for k in row) else "checked_at"
                row.setdefault(stamp, doc.get("checked_at"))
                key = row.get("poi_id") or row["name"]
                # a later file wins field by field (an hours-only row keeps the older price)
                ctx["web"][key] = {**ctx["web"].get(key, {}), **row}
        if fn.startswith("google_maps_check_") and fn.endswith(".json"):
            doc = _load(os.path.join(sources_dir, fn), {})
            for pid, it in (doc.get("items") or {}).items():
                ctx["gcheck"][pid] = {**it, "checked_at": doc.get("checked_at")}
            for it in doc.get("not_found") or []:
                ctx["gcheck"][it["poi_id"]] = {**it, "found": False, "checked_at": doc.get("checked_at")}
    return ctx


def migrate(v1_dir, out_dir, exports_dir, reports_dir, sources_dir):
    v1 = _load(os.path.join(v1_dir, "pois.json"))
    pois_v1 = v1["pois"]
    ctx = load_context(v1_dir, sources_dir)
    new_pois, new_cats, old_town, new_prices, skipped_new = load_new_pois(sources_dir, pois_v1)
    for row in new_prices:
        ctx["web"][row["poi_id"]] = row
    all_pois = pois_v1 + new_pois
    new_ids = {p["poi_id"] for p in new_pois}

    cats, cat_ev = {}, {}
    for p in all_pois:
        if p["poi_id"] in new_cats:
            cats[p["poi_id"]] = new_cats[p["poi_id"]]
            cat_ev[p["poi_id"]] = [f"curated_osm:{new_cats[p['poi_id']]}"]
        else:
            cats[p["poi_id"]], cat_ev[p["poi_id"]] = R.classify(p["name"], p.get("type"), p.get("cat"))
    defaults = category_defaults(pois_v1, cats)
    cluster, parent_of, alt = find_clusters(all_pois, cats)
    by_name = {p["name"]: p for p in all_pois}
    old_parent = by_name.get(OLD_TOWN_PARENT)
    if old_parent:
        anchor = by_name.get(OLD_TOWN_ANCHOR, old_parent)
        for p in all_pois:
            if R.ROLE_OF[cats[p["poi_id"]]] != "attraction":
                continue
            if R.haversine_m(anchor["lat"], anchor["lon"], p["lat"], p["lon"]) <= 600:
                cluster[p["poi_id"]] = "hoi_an_old_town"
            if p["poi_id"] in old_town:
                parent_of[p["poi_id"]] = old_parent
    for key, row in list(ctx["web"].items()):
        grp = row.get("apply_to_alt_group")
        for p in all_pois if grp else ():
            if alt.get(p["poi_id"]) == grp and p["name"] != key and p["poi_id"] not in ctx["web"] \
                    and p["name"] not in ctx["web"]:
                ctx["web"][p["poi_id"]] = {**row, "_via_alt_group": grp}
    ids = {p["poi_id"] for p in all_pois}
    unmatched = sorted(k for k in ctx["web"] if k not in by_name and k not in ids)
    if unmatched:
        print("WARN source rows not matched to any POI:", unmatched)

    decisions = load_decisions(sources_dir)
    human = load_human_verify(sources_dir)
    out, quarantine, notes, hours_conflict = [], {}, {}, set()
    for p in all_pois:
        pid, cat = p["poi_id"], cats[p["poi_id"]]
        is_new = pid in new_ids
        google = p.get("source") == GOOGLE_SOURCE
        arch = R.archetype_of(cat, p["name"], p.get("type"))
        parent = parent_of.get(pid)
        web_item = ctx["web"].get(pid) or ctx["web"].get(p["name"])
        osm_id, osm_dist, osm_tags, osm_how = osm_link(p, ctx)

        status, reason, pv_status, q_status = build_status(p, cat, pid)
        hours, pv_hours, q_hours = build_hours(p, arch, ctx, osm_tags, web_item)
        if hours["kind"] in ("safe_window", "unknown") and q_hours.get("opening_hours"):
            arch2, conflict = fit_archetype(
                p, cat, arch, hours, q_hours["opening_hours"],
                lambda a: build_hours(p, a, ctx, osm_tags, web_item)[0])
            if conflict:
                hours_conflict.add(pid)
            if arch2 != arch:
                arch = arch2
                hours, pv_hours, q_hours = build_hours(p, arch, ctx, osm_tags, web_item)
                pv_hours["note"] = "; ".join(x for x in (
                    pv_hours["note"], "nhóm giờ chọn lại cho khớp giờ Google Maps "
                                      "(giá trị Google chỉ ở quarantine)") if x)
        kind = R.dwell_kind(cat, p["name"], arch)
        price, pv_price, q_price = build_price(p, cat, arch, ctx, web_item, parent,
                                               cluster.get(pid) == "ba_na")
        dwell, pv_dwell, q_dwell = build_dwell(p, kind)
        tags, pv_tags = build_tags(p, cat, kind, dwell, defaults, is_new)

        tier = p.get("plan_tier")
        audience = {"main": "tourist", "wish_only": "tourist", "local": "local"}.get(tier)
        signature = bool(p.get("must_go")) or p["name"] in SIGNATURE_EXTRA
        pop = ctx["popularity"].get(pid) or {}
        wikidata = p.get("wikidata") or osm_tags.get("wikidata") or pop.get("wikidata")
        sitelinks, views = pop.get("wikidata_sitelinks"), pop.get("wikipedia_views_90d")
        prior, prior_by, prior_conf, prior_note = prize_prior(cat, signature, audience, wikidata,
                                                              sitelinks, views)
        if tier:
            prior_note += f"; plan_tier_v1={tier}"

        loc_src = {GOOGLE_SOURCE: "google_maps", "osm/overpass": "osm"}.get(p.get("source"), "manual")
        corroborated = osm_how in ("overpass_match", "osm_crosscheck", "v1_evidence") and \
            osm_dist is not None and osm_dist <= 60
        if loc_src == "osm":
            pv_loc = prov("osm", "open_data", note=p.get("_new_file"))
        elif corroborated:
            pv_loc = prov(loc_src, "open_data", confidence=0.65,
                          note=f"khớp OSM {osm_id} cách {osm_dist} m (toạ độ giữ nguyên)")
        else:
            pv_loc = prov(loc_src, "inferred", confidence=0.6,
                          note="toạ độ gốc Google — cần đối chiếu OSM" if loc_src == "google_maps"
                          else "nhập thủ công (web) — cần đối chiếu OSM")
        pv_name = prov(loc_src, pv_loc["verified_by"], confidence=pv_loc["confidence"],
                       note="tên khớp OSM" if corroborated else None)

        rec = {
            "poi_id": pid,
            "name": p["name"],
            "name_raw": p.get("name_osm") or p["name"],
            "name_en": p.get("name_en") or osm_tags.get("name:en"),
            "lat": p["lat"], "lon": p["lon"],
            "category": cat, "role": R.ROLE_OF[cat],
            "status": status, "status_reason": reason,
            "zone": R.zone_of(p["lat"], p["lon"]),
            "cluster_id": cluster.get(pid), "alt_group": alt.get(pid),
            "requires_ticket_of": parent["poi_id"] if parent else None,
            "hours": hours,
            "price": price,
            "dwell": dwell,
            "tags": tags,
            "time_profile": R.TIME_PROFILE[cat],
            "popularity": {"signature": signature, "audience": audience,
                           "prize_prior": None if cat == "lodging" else prior,
                           "wikidata_sitelinks": sitelinks, "wikipedia_views_90d": views},
            "description": {"text": None, "source": None, "license": None},
            "ext_ids": {"osm": osm_id, "wikidata": wikidata, "overture": None,
                        "google_place_id": pid if pid.startswith("ChIJ") else None},
            "provenance": {
                "name": pv_name,
                "location": pv_loc,
                "category": prov("curated_osm" if is_new else "rules_v2", "inferred",
                                 confidence=0.8 if cat_ev[pid][0].startswith(("override", "curated"))
                                 else 0.6,
                                 note=";".join(e for e in cat_ev[pid] if not e.startswith("type:"))
                                 or "theo loại địa điểm"),
                "status": pv_status,
                "hours": pv_hours,
                "price": pv_price,
                "dwell": pv_dwell,
                "tags": pv_tags,
                "popularity": prov("prize_prior_v2", prior_by, confidence=prior_conf,
                                   note=prior_note),
            },
            "data_version": DATA_VERSION, "valid_from": TODAY, "valid_to": None,
        }
        if pid in decisions:
            apply_decision(rec, decisions[pid])
        if pid in human:
            apply_human_verify(rec, human[pid])
        out.append(rec)

        q = {k: p[k] for k in GOOGLE_FIELDS if google and p.get(k) not in (None, "", [])}
        if google and isinstance(p.get("tags"), list) and p["tags"]:
            q["tags_v1"] = p["tags"]
        for part in (q_status, q_hours, q_price, q_dwell):
            q.update(part)
        note = v1_review_note(p)
        if note:
            notes[pid] = note        # Google content: decides keep/drop, never written
            if "review_count" not in q and review_count_of_note(note) is not None:
                q["review_count"] = review_count_of_note(note)
        g = ctx["gcheck"].get(pid)
        if g:
            q["gmaps_check"] = {k: g.get(k) for k in ("found", "gmaps_name", "rating", "review_count",
                                                      "hours_listed", "closed", "dist_m", "match",
                                                      "checked_at")}
        if q:
            quarantine[pid] = q

    inherit_parent_hours(out)
    for rec in out:
        reconcile(rec)
    out.sort(key=lambda r: r["poi_id"])
    n_built = len(out)
    out, dropped, curation = C.curate(out, quarantine, ctx["gcheck"], notes, hours_conflict, prov)
    for s in skipped_new:
        dropped.append({"poi_id": s["new"], "name": s["name"], "category": s["category"],
                        "zone": R.zone_of(s["lat"], s["lon"]), "rule": "duplicate",
                        "reason": f"trùng với '{s['existing_name']}'", "decided_by": "import_osm"})
    dropped.sort(key=lambda d: (C.RULES.index(d["rule"]), d["poi_id"]))
    kept_ids = {r["poi_id"] for r in out}
    quarantine = {k: v for k, v in quarantine.items() if k in kept_ids}
    by_rule = dict(sorted(Counter(d["rule"] for d in dropped).items(),
                          key=lambda kv: C.RULES.index(kv[0])))
    meta = {
        "snapshot": "danang-v2",
        "data_version": DATA_VERSION,
        "derived_from": f"danang-v1 ({len(pois_v1)} POI) + BE/data/sources",
        "built_at": TODAY,
        "built_by": "BE/ml/data/migrate_v2.py",
        "google_policy": "cach_ly: pois.json never holds a Google value (quarantine_google.json); "
                         "Google info only decides keep/drop (curate_v2.py)",
        "sources": ["danang-v1/pois.json", "danang-v1/hours_web.json", "danang-v1/price_web.json",
                    "danang-v1/osm_crosscheck.json"] + [f"sources/{f}" for f in ctx["files"]],
        "license_note": "OSM-derived values: ODbL 1.0, © OpenStreetMap contributors",
        "matrix": "matrix.json (dense-v1, BE/tools/build_matrix_v2.py)",
        "count": len(out),
        "count_candidates": len(pois_v1) + len(new_pois) + len(skipped_new),
        "count_v1_pois": len(pois_v1),
        "count_new_pois": len(new_pois),
        "count_dropped": len(dropped),
        "count_dropped_by_rule": by_rule,
        "count_by_status": dict(sorted(Counter(r["status"] for r in out).items())),
        "count_by_role": dict(sorted(Counter(r["role"] for r in out).items())),
        "count_by_category": dict(sorted(Counter(r["category"] for r in out).items())),
        "count_by_zone": dict(sorted(Counter(r["zone"] for r in out).items())),
        "count_by_price_tier": dict(sorted(Counter(str(r["price"]["tier"]) for r in out).items())),
        "count_by_hours_kind": dict(sorted(Counter(r["hours"]["kind"] for r in out).items())),
        "applied_decisions": len(decisions),
        "applied_human_verify": len(human),
        "pois": out,
    }
    _dump(os.path.join(out_dir, "pois.json"), meta)
    _dump(os.path.join(out_dir, "dropped.json"), {
        "note": "POI không giữ trong danang-v2 (mỗi POI một lý do, luật ở BE/ml/data/curate_v2.py). "
                "Muốn giữ lại một POI: thêm {\"status\": \"active\"} cho poi_id đó vào "
                "BE/data/sources/decisions_*.json rồi build lại (trừ lưu trú).",
        "data_version": DATA_VERSION, "count": len(dropped), "count_by_rule": by_rule,
        "items": dropped})
    _dump(os.path.join(out_dir, "quarantine_google.json"),
          {"note": "Giá trị gốc Google (SerpAPI / đọc từ Google Maps) của các POI được giữ. "
                   "KHÔNG dùng để train, xuất production hay hiển thị. Chỉ để đối chiếu nội bộ "
                   "và quyết giữ/bỏ POI.",
           "data_version": DATA_VERSION, "items": dict(sorted(quarantine.items()))})
    write_exports(out, exports_dir)
    write_reports(out, dropped, curation, quarantine, n_built, reports_dir)
    return meta


# --------------------------------------------------------------------------
# exports (always clean)
# --------------------------------------------------------------------------

FEATURE_COLS = [
    "poi_id", "name", "category", "role", "status", "zone", "cluster_id", "alt_group",
    "lat", "lon", "indoor", "effort", "kid_friendly", "party", "good_times", "time_budget",
    "on_request", "sun_exposure", "outdoor_exposure", "rain_cover", "weather_sensitive",
    "archetype", "time_profile", "hours_open", "hours_kind", "hours_conf", "hours_verified_by",
    "dwell_p25", "dwell_p50", "dwell_p75", "dwell_conf",
    "price_tier", "price_min_vnd", "price_max_vnd", "price_conf", "price_verified_by",
    "signature", "audience", "prize_prior", "osm_id", "wikidata",
]


def write_exports(pois, exports_dir):
    rows, weak = [], []
    for p in pois:
        pv, t = p["provenance"], p["tags"]
        rows.append({
            "poi_id": p["poi_id"], "name": p["name"], "category": p["category"],
            "role": p["role"], "status": p["status"], "zone": p["zone"],
            "cluster_id": p["cluster_id"], "alt_group": p["alt_group"],
            "lat": p["lat"], "lon": p["lon"],
            "indoor": t["indoor"], "effort": t["effort"], "kid_friendly": t["kid_friendly"],
            "party": "|".join(t["party"]), "good_times": "|".join(t["good_times"]),
            "time_budget": t["time_budget"], "on_request": t["on_request"],
            "sun_exposure": t["sun_exposure"], "outdoor_exposure": t["outdoor_exposure"],
            "rain_cover": t["rain_cover"], "weather_sensitive": t["weather_sensitive"],
            "archetype": p["hours"]["archetype"], "time_profile": p["time_profile"],
            "hours_open": "|".join(p["hours"]["open"]), "hours_kind": p["hours"]["kind"],
            "hours_conf": pv["hours"]["confidence"], "hours_verified_by": pv["hours"]["verified_by"],
            "dwell_p25": p["dwell"]["p25"], "dwell_p50": p["dwell"]["p50"],
            "dwell_p75": p["dwell"]["p75"], "dwell_conf": pv["dwell"]["confidence"],
            "price_tier": p["price"]["tier"], "price_min_vnd": p["price"]["min_vnd"],
            "price_max_vnd": p["price"]["max_vnd"], "price_conf": pv["price"]["confidence"],
            "price_verified_by": pv["price"]["verified_by"],
            "signature": p["popularity"]["signature"], "audience": p["popularity"]["audience"],
            "prize_prior": p["popularity"]["prize_prior"],
            "osm_id": p["ext_ids"]["osm"], "wikidata": p["ext_ids"]["wikidata"],
        })
        name_only = R.classify_name_only(p["name"])
        ev = pv["category"]["note"] or ""
        conf = 0.9 if ev.startswith(("override", "curated")) else (
            0.6 if name_only == p["category"] else 0.3)
        weak.append({"poi_id": p["poi_id"], "text": p["name"], "label": p["category"],
                     "label_name_only": name_only, "agree": name_only == p["category"],
                     "label_conf": conf, "status": p["status"]})
    _csv(os.path.join(exports_dir, "poi_features.csv"), rows, FEATURE_COLS)
    _csv(os.path.join(exports_dir, "poi_classifier_weak.csv"), weak,
         ["poi_id", "text", "label", "label_name_only", "agree", "label_conf", "status"])
    with open(os.path.join(exports_dir, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(EXPORT_README)


EXPORT_README = """# Exports `danang-v2` (training-safe)

Sinh bởi `BE/ml/data/migrate_v2.py` từ `BE/data/snapshots/danang-v2/pois.json` (v2.2).
**Không chứa giá trị gốc Google** (rating, số đánh giá, price_level, loại Google,
giờ/giá đọc từ Google Maps). Cột = các trường cùng tên trong
`docs/travelagent/DATA_SPEC.md`; `*_conf` / `*_verified_by` lấy từ `provenance`.

- `poi_features.csv`: một dòng mỗi POI, đặc trưng cho ranker / bộ lọc ứng viên / u(t).
  Giá trị ước lượng có `*_verified_by = inferred` và confidence thấp — đừng coi là nhãn.
- `poi_classifier_weak.csv`: nhãn yếu cho bộ phân loại POI. `label` = luật v2
  (tên trước); `label_conf >= 0.6` khi luật chỉ theo tên đồng ý. Người duyệt
  trước khi coi là gold.
"""


# --------------------------------------------------------------------------
# reports (for humans, regenerated each build)
# --------------------------------------------------------------------------

# Clean display name (gate G5); one definition, shared with the curation step.
name_problem = C.name_problem


def write_reports(pois, dropped, curation, quarantine, n_built, reports_dir):
    """Files for humans, regenerated each build: summary, dropped list, verify queue."""
    os.makedirs(reports_dir, exist_ok=True)
    _csv(os.path.join(reports_dir, "02_dropped.csv"), dropped,
         ["poi_id", "name", "category", "zone", "rule", "reason", "decided_by"])
    queue = verify_queue(pois)
    _csv(os.path.join(reports_dir, "11_verify_queue.csv"), queue,
         ["rank", "poi_id", "name", "category", "zone", "priority", "why", "hours_now",
          "hours_by", "price_now", "price_by", "maps_search"])
    write_queue_html(queue, os.path.join(reports_dir, "11_verify_queue.html"))
    zone_roles = defaultdict(Counter)
    for p in pois:
        zone_roles[p["zone"]][p["role"]] += 1

    def count(fn):
        return dict(sorted(Counter(str(fn(p)) for p in pois).items()))

    def dist(field):
        return count(lambda p: p["provenance"][field]["verified_by"])

    _dump(os.path.join(reports_dir, "01_build_summary.json"), {
        "built_at": TODAY, "data_version": DATA_VERSION,
        "candidates": len(pois) + len(dropped), "records_built": n_built,
        "kept": len(pois), "dropped": len(dropped),
        "dropped_by_rule": dict(sorted(Counter(d["rule"] for d in dropped).items(),
                                       key=lambda kv: C.RULES.index(kv[0]))),
        "kept_by_role": count(lambda p: p["role"]),
        "kept_by_category": count(lambda p: p["category"]),
        "kept_by_zone": count(lambda p: p["zone"]),
        "zone_roles": {z: dict(sorted(c.items())) for z, c in sorted(zone_roles.items())},
        "hours_kind": count(lambda p: p["hours"]["kind"]),
        "hours_verified_by": dist("hours"), "price_tier": count(lambda p: p["price"]["tier"]),
        "price_verified_by": dist("price"), "dwell_verified_by": dist("dwell"),
        "location_verified_by": dist("location"),
        "on_request": sum(1 for p in pois if p["tags"]["on_request"]),
        "audience": count(lambda p: p["popularity"]["audience"]),
        "signature": sum(1 for p in pois if p["popularity"]["signature"]),
        "osm_linked": sum(1 for p in pois if p["ext_ids"]["osm"]),
        "wikidata_linked": sum(1 for p in pois if p["ext_ids"]["wikidata"]),
        "quarantined_pois": len(quarantine),
        "google_evidence_of_kept": curation["evidence_via"],
        "names_fixed": curation["names_fixed"],
        "review_decided": curation["review_decided"],
    })


VERIFY_WEIGHT = {"paid_attraction": 1.0, "museum_indoor": 0.9, "beach": 0.8, "viewpoint": 0.8,
                 "religious": 0.5, "outdoor_landmark": 0.6, "night_market": 0.9,
                 "day_market": 0.7, "restaurant": 0.6, "cafe": 0.4, "nightlife": 0.4,
                 "wellness": 0.3}


def verify_queue(pois, limit=150):
    """Top POIs by importance x uncertainty; signature POIs first (gate G3)."""
    rows = []
    for p in pois:
        if p["status"] == "excluded" or p["role"] == "base":
            continue
        pv = p["provenance"]
        hc, pc = pv["hours"]["confidence"], pv["price"]["confidence"]
        unc = 1 - min(hc, pc)
        if unc < 0.3:
            continue
        imp = VERIFY_WEIGHT.get(p["category"], 0.3) + (0.8 if p["popularity"]["signature"] else 0)
        why = []
        if hc < 0.6:
            why.append(f"giờ {pv['hours']['verified_by']} {hc}")
        if pc < 0.6:
            why.append(f"giá {pv['price']['verified_by']} {pc}")
        if p["status"] == "review":
            why.append(f"review: {p['status_reason']}")
            imp += 0.3
        pr = p["price"]
        price_now = str(pr["tier"]) + (f" {pr['min_vnd']}-{pr['max_vnd']}" if pr["min_vnd"] is not None else "")
        rows.append({"poi_id": p["poi_id"], "name": p["name"], "category": p["category"],
                     "zone": p["zone"], "priority": round(imp * unc, 3), "why": "; ".join(why),
                     "hours_now": (", ".join(p["hours"]["open"]) or "—") + f" [{p['hours']['kind']}]",
                     "hours_by": pv["hours"]["verified_by"], "price_now": price_now,
                     "price_by": pv["price"]["verified_by"],
                     "maps_search": "https://www.google.com/maps/search/"
                                    + (p["name"] + " Đà Nẵng").replace(" ", "+")})
    rows.sort(key=lambda r: (-r["priority"], r["poi_id"]))
    for i, r in enumerate(rows[:limit], 1):
        r["rank"] = i
    return rows[:limit]


def write_queue_html(rows, path):
    head = ("<!doctype html><meta charset='utf-8'><title>Hàng đợi xác minh danang-v2</title>"
            "<style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse}"
            "td,th{border:1px solid #ccc;padding:4px 6px;vertical-align:top}"
            "th{background:#f3f3f3;position:sticky;top:0}input{width:9em}</style>"
            "<h1>Hàng đợi xác minh (top theo độ quan trọng × độ không chắc)</h1>"
            "<p>Mở link, sửa ô giờ/giá nếu sai, dán URL bằng chứng, bấm <b>Xuất JSON</b> "
            "và lưu thành <code>BE/data/sources/human_verify_v2_YYYYMMDD.json</code>.</p>"
            "<button onclick='exp()'>Xuất JSON</button><table><tr><th>#</th><th>Tên</th>"
            "<th>Loại/khu</th><th>Lý do</th><th>Giờ hiện tại</th><th>Giá hiện tại</th>"
            "<th>Giờ đúng (mọi ngày mở)</th><th>Mức giá / người (price.tier)</th>"
            "<th>URL bằng chứng</th><th>Tra</th></tr>")
    body = []
    for r in rows:
        body.append(
            f"<tr data-id='{html.escape(r['poi_id'])}'><td>{r['rank']}</td><td>{html.escape(r['name'])}</td>"
            f"<td>{r['category']}<br>{r['zone']}</td><td>{html.escape(r['why'])}</td>"
            f"<td>{html.escape(r['hours_now'])}<br><small>{r['hours_by']}</small></td>"
            f"<td>{html.escape(str(r['price_now']))}<br><small>{r['price_by']}</small></td>"
            "<td><input class=h placeholder='08:00-17:00'></td><td><select class=p>"
            "<option value=''>—</option><option>free</option><option>cheap</option>"
            "<option>medium</option><option>expensive</option><option>included</option>"
            "</select><input class=v placeholder='VND (tuỳ chọn)'></td>"
            "<td><input class=u></td>"
            f"<td><a href='{html.escape(r['maps_search'])}' target=_blank>maps</a></td></tr>")
    tail = ("</table><script>function exp(){const o=[];document.querySelectorAll('tr[data-id]')"
            ".forEach(t=>{const h=t.querySelector('.h').value,p=t.querySelector('.p').value,"
            "v=t.querySelector('.v').value,u=t.querySelector('.u').value;"
            "if(h||p||v)o.push({poi_id:t.dataset.id,hours:h||null,price_tier:p||null,"
            "ticket_vnd:v?Number(v):null,evidence_url:u||null,verified_by:'human',"
            "checked_at:new Date().toISOString().slice(0,10)})});const b=new Blob([JSON.stringify("
            "{items:o},null,1)],{type:'application/json'});const a=document.createElement('a');"
            "a.href=URL.createObjectURL(b);a.download='human_verify_v2.json';a.click()}</script>")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(head + "".join(body) + tail + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--v1", default=os.path.join("BE", "data", "snapshots", "danang-v1"))
    ap.add_argument("--out", default=os.path.join("BE", "data", "snapshots", "danang-v2"))
    ap.add_argument("--exports", default=os.path.join("BE", "data", "exports", "danang-v2"))
    ap.add_argument("--reports", default=os.path.join("reports", "p0"))
    ap.add_argument("--sources", default=os.path.join("BE", "data", "sources"))
    a = ap.parse_args(argv)
    meta = migrate(a.v1, a.out, a.exports, a.reports, a.sources)
    print(json.dumps({k: meta[k] for k in ("snapshot", "data_version", "count", "count_by_status",
                                            "count_by_hours_kind", "count_by_price_tier")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
