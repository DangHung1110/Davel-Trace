"""Build snapshot `danang-v2` from `danang-v1` (P0 data clean-up).

    python BE/ml/data/migrate_v2.py                       # default policy
    python BE/ml/data/migrate_v2.py --google-policy cach_ly

Reads (never writes) `BE/data/snapshots/danang-v1/`. Writes:

- `BE/data/snapshots/danang-v2/pois.json`      v1 superset + v2 fields
- `BE/data/snapshots/danang-v2/quarantine_google.json`  Google-derived values
- `BE/data/snapshots/danang-v2/matrix_ref.json` pointer to the v1 matrix
- `BE/data/exports/danang-v2/*.csv`            training-safe tables (no Google)
- `reports/p0/*`                               migration reports + verify queue

Google policy (`--google-policy`):

- `cach_ly` (clean): legacy top-level fields the app reads are filled only
  from clean sources (user, agent_web with URL, open data, rules). Google
  values stay in `quarantine_google.json`.
- `demo_phi_thuong_mai` (DEFAULT for now): same file layout, but when no
  clean value exists the legacy field falls back to the quarantined Google
  value, labelled `source=google_demo` in provenance. Needed today because
  ranking still reads `rating` (no clean popularity signal until P1).

Exports under `BE/data/exports/` are ALWAYS clean, whatever the policy.
Nothing here invents a per-POI fact: missing = null + low confidence.
"""

from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import difflib
import html
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import v2_rules as R  # noqa: E402

TODAY = "2026-11-18"
DATA_VERSION = "v2.1"
# DATA_SPEC_v2_1.md section 2: the ONLY top-level keys of a v2.1 POI (rule 11).
V21_KEYS = (
    "poi_id", "name", "name_raw", "name_en", "lat", "lon",
    "category", "role", "status", "status_reason", "zone", "cluster_id", "alt_group",
    "requires_ticket_of", "hours", "price", "dwell", "tags", "time_profile",
    "popularity", "description", "ext_ids", "provenance",
    "data_version", "valid_from", "valid_to",
)
PROVENANCE_KEYS = ("name", "location", "category", "hours", "price", "dwell", "tags", "popularity")
FIXED_HOURS_BY = ("human", "open_data", "user", "agent_web")
# smart_tags keys that are price, not tags (they fold into price.tier).
PRICE_TAG_KEYS = {"price_band", "band_source", "band_verified", "price_band_v1", "ticket",
                  "legacy_band_user", "price_band_source"}
TAG_RENAME = {"time": "good_times", "budget": "time_budget"}
POLICIES = ("cach_ly", "demo_phi_thuong_mai")
DEFAULT_POLICY = "demo_phi_thuong_mai"

# verified_by vocabulary -> default confidence
CONF = {"human": 0.9, "open_data": 0.7, "user": 0.7, "agent_web": 0.6,
        "google_demo": 0.5, "inferred": 0.45}
LEGACY_MIN_CONF = 0.6          # below this a value never reaches legacy fields

GOOGLE_FIELDS = ("rating", "price_level", "type", "ambience", "pros", "cons")

CLUSTERS = {
    # cluster_id: (parent name, anchor name, radius m)
    "ba_na": ("Sun World Bà Nà Hills", "Ba Na Hills", 1500),
    "ngu_hanh_son": ("Ngũ Hành Sơn", "Hòn Thủy Sơn", 800),
    "bay_mau": ("Rừng Dừa Bảy Mẫu", "Rừng Dừa Bảy Mẫu", 1000),
}
# Inside the Thủy Sơn ticket gate (reviewer judgement, needs human check).
NHS_TICKETED = {"Động Tàng Chơn", "Huyen Khong Cave", "Động Vân Thông",
                "Quốc Tự Tam Thai", "Hòn Thủy Sơn"}
SIGNATURE_EXTRA = {"Sun World Bà Nà Hills", "Cầu Rồng", "Bãi biển Mỹ Khê", "Ngũ Hành Sơn",
                   "Chợ Hàn", "Chợ Cồn", "Hải đăng Tiên Sa", "Cù Lao Chàm",
                   "VinWonders Nam Hội An", "Đèo Hải Vân", "Hải Vân Quan",
                   "Rừng Dừa Bảy Mẫu", "Phố đi bộ - chợ đêm Bạch Đằng Đà Nẵng",
                   "Phố cổ Hội An", "Chùa Cầu", "Thánh địa Mỹ Sơn", "Cầu Vàng",
                   "Nhà thờ Chính tòa Đà Nẵng", "Làng rau Trà Quế", "Chợ đêm Hội An"}
OSM_CAT = {"restaurant": "restaurant", "fast_food": "restaurant", "cafe": "cafe",
           "bar": "nightlife", "pub": "nightlife", "marketplace": "day_market",
           "museum": "museum_indoor", "place_of_worship": "religious", "park": "outdoor_landmark",
           "beach": "beach", "viewpoint": "viewpoint", "theme_park": "paid_attraction",
           "attraction": "outdoor_landmark", "gallery": "museum_indoor"}


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
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


def prov(source, verified_by, evidence_url=None, note=None, confidence=None,
         verified_at=None):
    c = CONF[verified_by] if confidence is None else confidence
    return {"source": source, "verified_by": verified_by,
            "confidence": round(float(c), 2), "evidence_url": evidence_url,
            "verified_at": verified_at, "note": note}


# --------------------------------------------------------------------------
# per-field builders
# --------------------------------------------------------------------------

def build_hours(p, category, archetype, hours_web, policy, access, web_item=None):
    """Return (hours_obj, legacy_opening_hours, provenance, quarantine_part)."""
    arch = R.ARCHETYPES[archetype]
    raw = list(p.get("opening_hours") or [])
    src = p.get("hours_source") or ""
    google_origin = p.get("source") == "serpapi/google-maps" and src in ("", None)
    every = R.intersect_all(raw)
    anyday = R.union_all(raw)
    conflict = bool(anyday) and not every
    osm = p.get("osm_evidence") or {}
    osm_week, closed_days = None, None
    if osm.get("hours") and osm_name_ok(p, osm):
        osm_week = R.parse_osm_hours(osm["hours"])

    chosen, pv, weekly = None, None, None
    hw = hours_web.get(p["name"]) or {}
    wi_spans = R.parse_element((web_item or {}).get("hours") or "")
    if src == "user-verify" and every:
        chosen, pv = every, prov("user_review", "user")
    elif wi_spans:
        chosen = wi_spans
        pv = prov("web", "agent_web", evidence_url=web_item.get("evidence_url"),
                  note=web_item.get("note"), verified_at=web_item.get("checked_at"),
                  confidence=web_item.get("confidence", 0.6))
    elif src == "web" and every:
        url = next(iter(hw.get("price_sources") or []), None)
        note = hw.get("hours_web") or (p.get("web_evidence") or {}).get("hours_web")
        chosen = every
        pv = prov("web", "agent_web", evidence_url=url, note=note,
                  confidence=0.6 if url else 0.5)
    elif src == "osm-converted" and every:
        chosen, pv = every, prov("osm", "open_data", evidence_url=osm.get("osm"))
    elif p.get("source") == "osm/overpass" and every:
        chosen, pv = every, prov("osm", "open_data")
    elif osm_week is not None:
        weekly = {d: R.fmt(s)[0] if s else "off" for d, s in osm_week.items()}
        wi = R.week_intersection(osm_week)
        note = f"OSM opening_hours='{osm['hours']}', khớp {osm.get('dist_m')} m"
        closed_days = []
        if not wi:
            wi, closed_days = R.open_days_intersection(osm_week)
            if wi and closed_days:
                note += f"; đóng cửa {','.join(closed_days)} (lịch chưa xét thứ trong tuần)"
        if wi and google_origin and every and policy == "demo_phi_thuong_mai":
            both = R.intersect(wi, every)
            if both and both != wi:
                wi, note = both, note + "; lệch Google -> lấy phần giao (an toàn cho cả hai)"
        if wi:
            chosen = wi
            pv = prov("osm", "open_data", evidence_url=f"https://www.openstreetmap.org/{osm['osm']}",
                      note=note, confidence=0.65)
    elif src == "rule_open_access" and every:
        chosen, pv = every, prov("rule_open_access", "inferred", confidence=0.55,
                                 note="không gian mở, không cổng")
    elif src == "rule_temple_default" and every:
        chosen, pv = every, prov("rule_temple_default", "inferred")

    quarantine = {}
    if google_origin and raw:
        quarantine["opening_hours"] = raw
        if chosen is None and policy == "demo_phi_thuong_mai" and every:
            chosen, pv = every, prov("google_maps", "google_demo",
                                     note="giờ chung mọi ngày (giao các biến thể)")

    safe = [s for w in arch["safe"] for s in R.parse_element(w)]
    if chosen is None:
        if safe:
            chosen = safe
            pv = prov(f"archetype:{archetype}", "inferred",
                      note="khung an toàn theo nhóm giờ — nên kiểm tra giờ thật")
        else:
            pv = prov("none", "inferred", confidence=0.0,
                      note="KHÔNG XÁC ĐỊNH — cần tra trang chính thức")

    final = chosen or []
    if access and final:
        final = R.intersect(final, access)
    hours = {
        "spans": R.fmt(chosen)[0].split(", ") if chosen else [],
        "weekly": weekly,
        "spans_any_day": R.fmt(anyday)[0].split(", ") if anyday else [],
        "raw_v1": raw,
        "conflict": conflict,
        "archetype": archetype,
        "archetype_default": arch["default"],
        "safe_windows": arch["safe"],
        "access_window": R.fmt(access)[0].split(", ") if access else None,
        "closed_days": closed_days or None,
    }
    return hours, R.fmt(final), pv, quarantine


def osm_name_ok(p, osm, max_m=60, min_ratio=0.6):
    """An OSM element counts as the same place only if it is close AND its
    name matches. v1 `osm_evidence` was joined by distance alone, which paired
    e.g. 'House Coffee' with 'The Pizza Company' 42 m away."""
    dist = osm.get("dist_m")
    if dist is None or dist > max_m or not osm.get("name"):
        return False
    a, b = R.fold(p["name"]), R.fold(osm["name"])
    if not a or not b:
        return False
    return a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= min_ratio


def _range_vnd(rng):
    if not rng:
        return None
    return {k: (int(v) if v is not None else None) for k, v in rng.items()}


def build_price(p, category, archetype, price_web, web_tickets, policy, in_paid_cluster):
    """Return (price_obj, provenance, quarantine_part)."""
    name = p["name"]
    q = {}
    pw = price_web.get(name) or {}
    wt = web_tickets.get(p["poi_id"]) or web_tickets.get(name) or {}
    urls = list(pw.get("price_sources") or p.get("price_sources") or [])
    note = p.get("price_note") or ""
    ticket_note = p.get("ticket_note") or pw.get("ticket_note")
    out = {"basis": "per_person", "min_vnd": None, "max_vnd": None,
           "typical_vnd": None, "band": None, "ticket_vnd": None,
           "free_entry": None, "status": "unknown", "note": ticket_note}
    pv = None

    if category == "lodging":
        # Lodging is the trip base, not a stop: its Google figure is a room
        # rate per night, never mixed into per-person activity spend.
        out.update(basis="per_night_room", status="not_applicable")
        g = R.parse_google_price(note)
        if g:
            q["price_range"] = _range_vnd(g)
            q["price_note"] = note
            if policy == "demo_phi_thuong_mai":
                out.update(typical_vnd=R.typical_of(g), min_vnd=g.get("min"), max_vnd=g.get("max"))
                for k in ("min_vnd", "max_vnd", "typical_vnd"):
                    if out.get(k) is not None:
                        out[k] = int(round(out[k]))
                return out, prov("google_maps", "google_demo", note="giá phòng/đêm"), q
        return out, prov("n/a", "inferred", confidence=0.0), q
    if p.get("requires_ticket_of") and R.ROLE_OF.get(category) == "attraction":
        out.update(basis="included_in_parent", status="known", free_entry=False)
        return out, prov("cluster_rule", "inferred", confidence=0.6,
                         note=f"vé tính ở {p['requires_ticket_of_name']}"), q

    if category in ("paid_attraction", "museum_indoor"):
        out["basis"] = "ticket"

    g = R.parse_google_price(note)
    if g:
        q["price_range"] = _range_vnd(g)
        q["price_note"] = note

    if wt.get("ticket_vnd") is not None or wt.get("free_entry"):
        tv = wt.get("ticket_vnd")
        out.update(ticket_vnd=tv, typical_vnd=wt.get("typical_vnd", tv),
                   min_vnd=wt.get("min_vnd", tv), max_vnd=wt.get("max_vnd", tv), status="known",
                   free_entry=bool(wt.get("free_entry")), note=wt.get("note") or ticket_note)
        if wt.get("_via_alt_group"):
            out["note"] = f"[giá chung nhóm {wt['_via_alt_group']}] " + (wt.get("note") or "")
        pv = prov("web", "agent_web", evidence_url=wt.get("evidence_url"),
                  note=out["note"], verified_at=wt.get("checked_at"),
                  confidence=(wt.get("confidence", 0.6) if wt.get("evidence_url") else 0.5)
                  - (0.05 if wt.get("_via_alt_group") else 0))
    elif p.get("ticket_vnd"):
        tv = int(p["ticket_vnd"])
        is_user = "user" in (ticket_note or "")
        out.update(ticket_vnd=tv, typical_vnd=tv, min_vnd=tv, max_vnd=tv, status="known",
                   free_entry=False)
        pv = prov("user_review" if is_user else "web", "user" if is_user else "agent_web",
                  evidence_url=urls[0] if urls else None, note=ticket_note,
                  confidence=0.7 if is_user else (0.6 if urls else 0.5))
    elif note.startswith("user:"):
        rng = R.parse_user_price(note)
        if rng:
            out.update(min_vnd=rng.get("min"), max_vnd=rng.get("max"),
                       typical_vnd=R.typical_of(rng), status="known")
            pv = prov("user_review", "user", note=note)
    elif pw.get("price_band") and urls:
        # v1 web review gave only a 3-level band; keep the band, no numbers.
        out.update(status="band_only", note=ticket_note,
                   free_entry=(pw.get("ticket") is False and category in R.FREE_PUBLIC) or None)
        out["legacy_band_web"] = pw["price_band"]
        pv = prov("web", "agent_web", evidence_url=urls[0], note=ticket_note, confidence=0.55)

    if pv is None and g and policy == "demo_phi_thuong_mai":
        out.update(min_vnd=g.get("min"), max_vnd=g.get("max"),
                   typical_vnd=R.typical_of(g), status="known")
        pv = prov("google_maps", "google_demo", note=note)

    if pv is None:
        ticket_flag = (p.get("smart_tags") or {}).get("ticket")
        if category in R.FREE_PUBLIC and not ticket_flag and not in_paid_cluster:
            out.update(free_entry=True, min_vnd=0, max_vnd=0, typical_vnd=0,
                       basis="entry", status="known")
            pv = prov("rule_free_public", "inferred", confidence=0.7,
                      note="nơi công cộng (biển/chùa/công viên/điểm ngắm) — vào cửa tự do")
        elif category == "restaurant":
            f = R.fold(p["name"]) + " " + R.fold(p.get("type"))
            rng = dict(R.RESTAURANT_PRICE[archetype if archetype in R.RESTAURANT_PRICE else "nha_hang"])
            if R._has(f, R.HIGH_END_KEYS):
                rng = {"min": 200_000, "max": 600_000}
            out.update(min_vnd=rng["min"], max_vnd=rng["max"],
                       typical_vnd=(rng["min"] + rng["max"]) / 2, status="estimate")
            pv = prov(f"category_default:{archetype}", "inferred", confidence=0.4,
                      note="ƯỚC LƯỢNG theo kiểu quán")
        elif category == "paid_attraction" and R._has(R.fold(p["name"]), ("cooking", "class", "workshop")):
            out.update(min_vnd=750_000, max_vnd=1_100_000, typical_vnd=900_000, status="estimate")
            pv = prov("category_default:cooking_class", "inferred", confidence=0.45,
                      note="ƯỚC LƯỢNG: lớp nấu ăn Đà Nẵng US$29-40/người (cookly/pelago 11/2026)")
        elif category in R.CATEGORY_PRICE:
            rng = R.CATEGORY_PRICE[category]
            out.update(min_vnd=rng["min"], max_vnd=rng["max"],
                       typical_vnd=(rng["min"] + rng["max"]) / 2, status="estimate")
            pv = prov(f"category_default:{category}", "inferred", confidence=0.4,
                      note="ƯỚC LƯỢNG theo thể loại")
        else:
            out["status"] = "todo" if category in ("paid_attraction", "museum_indoor") else "unknown"
            pv = prov("none", "inferred", confidence=0.0,
                      note="KHÔNG XÁC ĐỊNH — giá vé phải tra trang chính thức (không đoán)")

    for k in ("min_vnd", "max_vnd", "typical_vnd", "ticket_vnd"):
        if out.get(k) is not None:
            out[k] = int(round(out[k]))
    if out.get("free_entry"):
        out["band"] = "re"
    elif out.get("typical_vnd") is not None:
        out["band"] = R.band_of(out["typical_vnd"])
    elif out.get("min_vnd") is not None:
        out["band"] = R.band_of(out["min_vnd"])
    return out, pv, q


def price_tier(price, category):
    """v2.0 price object -> one `price.tier` (DATA_SPEC_v2_1 price table).

    included = inside a parent ticket; free = explicit free entry; a VND
    figure (known or estimate) -> tier by the 4-level table; a web/user band
    without numbers keeps its 3-level name; nothing known -> None.
    """
    from BE.common import tier_of_vnd
    if category == "lodging" or price.get("status") == "not_applicable":
        return None
    if price.get("basis") == "included_in_parent":
        return "included"
    if price.get("free_entry"):
        return "free"
    for k in ("typical_vnd", "ticket_vnd", "min_vnd"):
        if price.get(k) is not None:
            return tier_of_vnd(price[k])
    band = price.get("legacy_band_web") or price.get("legacy_band_user")
    return band if band in ("cheap", "medium", "expensive") else None


# WP6: clean ranking prior per category (role prior), no Google input.
CATEGORY_PRIOR = {
    "beach": 0.6, "viewpoint": 0.55, "outdoor_landmark": 0.5, "religious": 0.45,
    "museum_indoor": 0.5, "day_market": 0.5, "night_market": 0.55, "paid_attraction": 0.55,
    "restaurant": 0.45, "cafe": 0.4, "nightlife": 0.35, "wellness": 0.3, "lodging": 0.0,
}


def prize_prior(category, signature, wikidata, sitelinks, views):
    """`popularity.prize_prior` in [0,1] + (verified_by, confidence, note).

    Weighted clean signals (DATA_FIX_PLAN WP6): category prior, approved
    signature list, Wikidata presence/sitelinks, Wikipedia 90-day views
    (log-scaled). Missing sources lower the confidence, they never invent a
    value. Google rating is NOT an input.
    """
    import math
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
    p = round(min(1.0, p), 3)
    rich = bool(sitelinks or views)
    return p, ("open_data" if rich else "inferred"), (0.6 if rich else 0.4), "; ".join(parts)


def to_v21(v, p_src, pv_hours, legacy_hours, quarantine_entry):
    """Internal v2.0 record -> (v2.1 record, archive dict).

    The v2.1 record holds exactly `V21_KEYS`; everything else that is not a
    Google value goes to the archive (traceability only, never read at run
    time). Google values live in `quarantine_entry` (filled by the caller).
    """
    google_src = p_src.get("source") == "serpapi/google-maps"
    h, pr, dw = v["hours"], v["price"], v["dwell"]
    open_ = legacy_hours[0].split(", ") if legacy_hours else []
    kind = ("unknown" if not open_ else
            "fixed" if pv_hours["verified_by"] in FIXED_HOURS_BY else "safe_window")
    tier = price_tier(pr, v["category"])

    st = {TAG_RENAME.get(k, k): val for k, val in (p_src.get("smart_tags") or {}).items()
          if k not in PRICE_TAG_KEYS}
    base = v["tags"]                                  # build_tags() output
    tags = {**st, "indoor": base["indoor"], "effort": base["effort"],
            "kid_friendly": base["kid_friendly"],
            "weather_sensitive": bool(base["weather_sensitive"])}

    pv = dict(v["provenance"])
    v1_verified = pv.pop("v1_verified", None)
    pv_price = dict(pv["price"])
    nums = [f"{k}={pr[k]}" for k in ("ticket_vnd", "min_vnd", "max_vnd", "typical_vnd")
            if pr.get(k) is not None]
    if nums:
        pv_price["note"] = "; ".join(x for x in (pv_price.get("note"), "VND " + ", ".join(nums)) if x)
    pv["price"] = pv_price
    pop_src = v["popularity"]
    wd = v["ext_ids"].get("wikidata")
    prior, prior_by, prior_conf, prior_note = prize_prior(
        v["category"], pop_src["signature"], wd, pop_src.get("wikidata_sitelinks"),
        pop_src.get("wikipedia_views_90d"))
    pv["popularity"] = prov("prize_prior_v1:category+signature+wikidata+wikipedia", prior_by,
                            confidence=prior_conf, note=prior_note)
    rec = {
        "poi_id": v["poi_id"],
        "name": v["name"],
        "name_raw": p_src.get("name_osm") or p_src["name"],
        "name_en": v.get("name_en"),
        "lat": v["lat"], "lon": v["lon"],
        "category": v["category"], "role": v["role"],
        "status": v["status"], "status_reason": v["status_reason"],
        "zone": v["zone"], "cluster_id": v["cluster_id"], "alt_group": v["alt_group"],
        "requires_ticket_of": v["requires_ticket_of"],
        "hours": {"open": open_, "kind": kind, "closed_days": h.get("closed_days") or [],
                  "access_window": h.get("access_window"), "archetype": h["archetype"]},
        "price": {"tier": tier, "note": pr.get("note")},
        "dwell": {k: dw[k] for k in ("p25", "p50", "p75")},
        "tags": tags,
        "time_profile": v["time_profile"],
        "popularity": {"signature": pop_src["signature"],
                       "prize_prior": None if v["category"] == "lodging" else prior,
                       "wikidata": wd, "wikidata_sitelinks": pop_src.get("wikidata_sitelinks"),
                       "wikipedia_views_90d": pop_src.get("wikipedia_views_90d")},
        "description": v["description"],
        "ext_ids": {"osm": v["ext_ids"].get("osm"),
                    "google_place_id": v["poi_id"] if v["poi_id"].startswith("ChIJ") else None,
                    "overture": v["ext_ids"].get("overture")},
        "provenance": {k: pv[k] for k in PROVENANCE_KEYS},
        "data_version": DATA_VERSION, "valid_from": v["valid_from"], "valid_to": v["valid_to"],
    }
    skip = set(V21_KEYS) | set(GOOGLE_FIELDS) | {"opening_hours", "smart_tags", "hours",
                                                "price", "dwell", "tags", "provenance",
                                                "popularity", "ext_ids", "description"}
    if google_src:
        skip |= {"price_note"}
    archive = {k: val for k, val in v.items() if k not in skip}
    archive["smart_tags_price"] = {k: val for k, val in (p_src.get("smart_tags") or {}).items()
                                   if k in PRICE_TAG_KEYS}
    archive["hours_v20"] = {k: val for k, val in h.items()
                            if k not in ("archetype", "closed_days", "access_window")
                            and not (google_src and k in ("raw_v1", "spans_any_day", "conflict"))}
    archive["price_v20"] = {k: val for k, val in pr.items() if k != "note"}
    archive["dwell_v20"] = {k: val for k, val in dw.items() if k not in ("p25", "p50", "p75")}
    archive["ext_ids_v20"] = {k: val for k, val in v["ext_ids"].items() if k not in ("osm", "overture")}
    archive["v1_verified"] = v1_verified
    if not google_src and isinstance(p_src.get("tags"), list):
        archive["tags_v1"] = p_src["tags"]
    if google_src and isinstance(p_src.get("tags"), list) and p_src["tags"]:
        quarantine_entry["tags_v1"] = p_src["tags"]
    return rec, archive


def load_decisions(sources_dir):
    """{poi_id: {name?, status?, status_reason?, category?}} from
    BE/data/sources/decisions_*.json (user-approved review/name decisions;
    later files override earlier ones)."""
    out = {}
    if os.path.isdir(sources_dir):
        for fn in sorted(os.listdir(sources_dir)):
            if fn.startswith("decisions_") and fn.endswith(".json"):
                for pid, d in (_load(os.path.join(sources_dir, fn), {}) or {}).get("items", {}).items():
                    out.setdefault(pid, {}).update({**d, "_file": fn})
    return out


def load_human_verify(sources_dir):
    """{poi_id: item} from BE/data/sources/human_verify_v2_*.json (verify-queue
    export: hours, price_tier or ticket_vnd, evidence_url, checked_at)."""
    out = {}
    if os.path.isdir(sources_dir):
        for fn in sorted(os.listdir(sources_dir)):
            if fn.startswith("human_verify_v2_") and fn.endswith(".json"):
                for it in (_load(os.path.join(sources_dir, fn), {}) or {}).get("items", []):
                    out[it["poi_id"]] = {**it, "_file": fn}
    return out


def apply_decision(rec, d):
    """User decision (WP5 names, WP10 review/duplicates) -> v2.1 record."""
    pv = rec["provenance"]
    if d.get("name"):
        rec["name"] = d["name"]
        pv["name"] = prov("user_decision", "user", note=f"{d['_file']}; tên gốc trong name_raw")
    if d.get("status") in ("active", "review", "excluded"):
        rec["status"] = d["status"]
        rec["status_reason"] = d.get("status_reason") if d["status"] != "active" else None
    if d.get("category") in R.ALL_CATEGORIES:
        rec["category"], rec["role"] = d["category"], R.ROLE_OF[d["category"]]
        pv["category"] = prov("user_decision", "user", note=d["_file"])


def apply_human_verify(rec, it):
    """Human-checked hours/price (WP8). `human` needs an evidence URL,
    otherwise the value is recorded as `user` (DATA_SPEC_v2_1 verified_by)."""
    from BE.common import PRICE_TIERS, tier_of_vnd
    url = it.get("evidence_url")
    by = "human" if url else "user"
    when = it.get("checked_at") or TODAY
    if it.get("hours"):
        spans = [s.strip() for s in str(it["hours"]).split(",") if s.strip()]
        if spans and all(R.parse_span(s) for s in spans):
            rec["hours"]["open"], rec["hours"]["kind"] = spans, "fixed"
            rec["provenance"]["hours"] = prov("human_verify", by, evidence_url=url,
                                              verified_at=when, note=it["_file"])
    tier = it.get("price_tier")
    if tier is None and it.get("ticket_vnd") is not None:
        tier = tier_of_vnd(it["ticket_vnd"])
    if tier in PRICE_TIERS and not (tier == "included") ^ bool(rec["requires_ticket_of"]):
        rec["price"]["tier"] = tier
        note = it["_file"] + (f"; VND {it['ticket_vnd']}" if it.get("ticket_vnd") is not None else "")
        rec["provenance"]["price"] = prov("human_verify", by, evidence_url=url,
                                          verified_at=when, note=note)


def build_tags(p, category):
    st = p.get("smart_tags") or {}
    space = st.get("space") or p.get("space")
    indoor = {"indoor": True, "outdoor": False}.get(space)
    party = st.get("party") or []
    kid = None if not party else ("family" in party and category != "nightlife")
    return {
        "indoor": indoor,
        "space": space,
        "kid_friendly": kid,
        "effort": p.get("intensity"),
        "sun_exposure": st.get("sun_exposure"),
        "rain_cover": st.get("rain_cover"),
        "time_of_day": st.get("time"),
        "weather_sensitive": p.get("weather_sensitive"),
    }


# --------------------------------------------------------------------------
# main build
# --------------------------------------------------------------------------

def find_clusters(pois, cats):
    by_name = {p["name"]: p for p in pois}
    cluster, parent_of, alt = {}, {}, {}
    for cid, (parent, anchor, radius) in CLUSTERS.items():
        if parent not in by_name or anchor not in by_name:
            continue
        a = by_name[anchor]
        for p in pois:
            if cats[p["poi_id"]] in ("lodging",):
                continue
            d = R.haversine_m(a["lat"], a["lon"], p["lat"], p["lon"])
            if d > radius:
                continue
            role = R.ROLE_OF[cats[p["poi_id"]]]
            if cid == "bay_mau":
                f = R.fold(p["name"])
                if not any(k in f for k in ("dua", "thuyen thung", "basket")):
                    continue
                alt[p["poi_id"]] = "bay_mau"
            if role != "attraction" and cid != "ba_na":
                continue
            cluster[p["poi_id"]] = cid
            if cid == "ba_na" and p["name"] != parent:
                parent_of[p["poi_id"]] = by_name[parent]
            if cid == "ngu_hanh_son" and p["name"] in NHS_TICKETED:
                parent_of[p["poi_id"]] = by_name[parent]
    if "Ba Na Hills" in by_name:
        alt[by_name["Ba Na Hills"]["poi_id"]] = "ba_na_entry"
        alt[by_name["Sun World Bà Nà Hills"]["poi_id"]] = "ba_na_entry"
    return cluster, parent_of, alt


def find_duplicates(pois, max_m=150, min_ratio=0.72):
    generic = {"chua", "nha", "tho", "giao", "xu", "bai", "bien", "tam", "quan",
               "ca", "phe", "cafe", "coffee", "nha hang", "da", "nang", "spa", "cho",
               "beach", "the", "va", "and", "dong", "hotel", "khach", "san"}

    def key(n):
        return " ".join(w for w in R.fold(n).split() if w not in generic)

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



# --------------------------------------------------------------------------
# new POIs from open data (BE/data/sources/new_pois_*.json)
# --------------------------------------------------------------------------

def _base_from_osm(item, name, fetched_at):
    """v1-shaped record for an OSM element, built by the existing osm_add
    pipeline (duration prior, smart_tags) when importable, else minimal."""
    otype, oid = item["osm"].split("/")
    tags = {"opening_hours": item.get("oh") or ""}
    try:
        from BE.ml.data.osm_add import to_poi
        p = to_poi({"type": otype, "id": int(oid)}, item.get("c") or "?", item["lat"], item["lon"],
                   name, tags)
    except Exception as e:  # noqa: BLE001 - fall back, never block the build
        print("WARN osm_add.to_poi unavailable:", type(e).__name__, e)
        p = {"poi_id": f"osm:{item['osm']}", "name": name, "type": item.get("c") or "?",
             "lat": item["lat"], "lon": item["lon"], "visit_min": {"p25": 30, "p50": 60, "p75": 90},
             "dur_source": "category_rule", "dur_confidence": "low", "price_level": 2, "fee": 0,
             "rating": None, "tags": [], "source": "osm/overpass", "verified": False,
             "intensity": 2, "weather_sensitive": False, "smart_tags": {}}
    p["fetched_at"] = fetched_at
    p["opening_hours"] = []           # hours come from the weekly OSM parser
    p["hours_source"] = ""
    p["name_osm"] = item["name"]
    p["osm_evidence"] = {"osm": item["osm"], "dist_m": 0.0, "hours": item.get("oh"),
                         "fee": item.get("fee"), "name": name}
    p["added_in"] = "v2.0-p0b"
    return p


def load_new_pois(sources_dir, existing):
    """-> (new POI records, curated category by poi_id, old-town ticket ids,
    price rows, wikidata by poi_id, skipped duplicates)."""
    new, cats, old_town, prices, wikidata, skipped = [], {}, set(), [], {}, []
    if not os.path.isdir(sources_dir):
        return new, cats, old_town, prices, wikidata, skipped
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
            dup = None
            for q in existing:
                if abs(q["lat"] - it["lat"]) > 0.001 or abs(q["lon"] - it["lon"]) > 0.001:
                    continue
                if R.haversine_m(q["lat"], q["lon"], it["lat"], it["lon"]) <= 100 and osm_name_ok(
                        {"name": q["name"]}, {"name": name, "dist_m": 0}, min_ratio=0.7):
                    dup = q
                    break
            if dup:
                skipped.append({"new": pid, "name": name, "existing": dup["poi_id"],
                                "existing_name": dup["name"]})
                continue
            p = _base_from_osm(it, name, doc.get("fetched_at", TODAY))
            new.append(p)
            have.add(pid)
            cats[pid] = cur.get("category", {}).get(it["osm"]) or OSM_CAT.get(it.get("c"), "outdoor_landmark")
            if it.get("wd"):
                wikidata[pid] = it["wd"]
        old_town |= {f"osm:{x}" for x in cur.get("old_town_ticket", [])}
        for row in doc.get("prices", []):
            prices.append({**row, "checked_at": doc.get("fetched_at")})
    return new, cats, old_town, prices, wikidata, skipped


def migrate(v1_dir, out_dir, exports_dir, reports_dir, policy, sources_dir):
    assert policy in POLICIES, policy
    # v2.1: pois.json is ALWAYS clean; Google values are only in quarantine and
    # the policy is applied at RUN time by BE.common.poi_view (GOOGLE_POLICY).
    runtime_policy, policy = policy, "cach_ly"
    v1 = _load(os.path.join(v1_dir, "pois.json"))
    pois_v1 = v1["pois"]
    price_web = _load(os.path.join(v1_dir, "price_web.json"), {})
    hours_web = _load(os.path.join(v1_dir, "hours_web.json"), {})
    geo = {g["poi_id"]: g for g in _load(os.path.join(v1_dir, "geo_answers.json"), [])}
    web_tickets = {}
    for fn in sorted(os.listdir(sources_dir)) if os.path.isdir(sources_dir) else []:
        if fn.startswith("agent_web_") and fn.endswith(".json"):
            src_doc = _load(os.path.join(sources_dir, fn), {})
            for row in src_doc.get("items", []):
                row.setdefault("checked_at", src_doc.get("checked_at"))
                web_tickets[row.get("poi_id") or row["name"]] = row
    popularity = _load(os.path.join(sources_dir, "popularity.json"), {}) or {}
    osm_match = (_load(os.path.join(sources_dir, "osm_match.json"), {}) or {}).get("items", {})

    new_pois, new_cats, old_town, new_prices, new_wd, skipped_new = load_new_pois(sources_dir, pois_v1)
    for row in new_prices:
        web_tickets[row["poi_id"]] = row
    for pid, qid in new_wd.items():
        popularity.setdefault(pid, {})["wikidata"] = qid
    v1_ids = {p["poi_id"] for p in pois_v1}
    pois_v1 = pois_v1 + new_pois

    cats, cat_ev = {}, {}
    for p in pois_v1:
        if p["poi_id"] in new_cats:
            cats[p["poi_id"]] = new_cats[p["poi_id"]]
            cat_ev[p["poi_id"]] = [f"curated_osm:{new_cats[p['poi_id']]}"]
            continue
        c, ev = R.classify(p["name"], p.get("type"), p.get("cat"))
        cats[p["poi_id"]], cat_ev[p["poi_id"]] = c, ev
    cluster, parent_of, alt = find_clusters(pois_v1, cats)
    old_town_parent = next((p for p in new_pois if p["name"] == "Phố cổ Hội An"), None)
    if old_town_parent:
        anchor = next((p for p in new_pois if p["name"] == "Chùa Cầu"), old_town_parent)
        for p in pois_v1:
            if R.ROLE_OF[cats[p["poi_id"]]] != "attraction":
                continue
            if R.haversine_m(anchor["lat"], anchor["lon"], p["lat"], p["lon"]) <= 600:
                cluster[p["poi_id"]] = "hoi_an_old_town"
            if p["poi_id"] in old_town:
                parent_of[p["poi_id"]] = old_town_parent
    by_name = {p["name"]: p for p in pois_v1}
    for key, row in list(web_tickets.items()):
        grp = row.get("apply_to_alt_group")
        if not grp:
            continue
        for p in pois_v1:
            if alt.get(p["poi_id"]) == grp and p["name"] != key and p["poi_id"] not in web_tickets \
                    and p["name"] not in web_tickets:
                web_tickets[p["poi_id"]] = {**row, "_via_alt_group": grp}
    unknown_sources = [k for k in web_tickets if k not in by_name
                       and not any(p["poi_id"] == k for p in pois_v1)]
    if unknown_sources:
        print("WARN source rows not matched to any POI:", unknown_sources)
    dups = find_duplicates(pois_v1)

    out_pois, quarantine, changes, review_rows = [], {}, [], []
    v21, archive = [], {}
    decisions = load_decisions(sources_dir)     # WP5 / WP10 (user-approved)
    human = load_human_verify(sources_dir)      # WP8 (verify queue export)
    for p in pois_v1:
        pid = p["poi_id"]
        v = copy.deepcopy(p)
        cat = cats[pid]
        excl = R.exclusion_reason(p["name"], p.get("type"))
        rev = R.review_reason(p["name"], cat, pid, p.get("type"))
        status = "excluded" if excl else ("review" if rev else "active")
        if cat == "lodging":
            status = "active"   # kept as trip base; role=base filters it
        arch = R.archetype_of(cat, p["name"], p.get("type"))
        access = None
        on_peninsula = p["lat"] >= 16.095 and p["lon"] >= 108.245
        if "07:30-18:30" in (p.get("access_note") or "") and on_peninsula:
            # Sơn Trà peninsula road window; Oct-Feb is 07:30-17:30. Use the
            # stricter one all year (conservative; source in access_note).
            access = R.parse_element("07:30-17:30")
        parent = parent_of.get(pid)
        v["requires_ticket_of"] = parent["poi_id"] if parent else None
        v["requires_ticket_of_name"] = parent["name"] if parent else None

        web_item = web_tickets.get(pid) or web_tickets.get(p["name"])
        om = osm_match.get(pid)
        if om and not (p.get("osm_evidence") or {}).get("hours"):
            # fresh Overpass match (fetch_open_data.py) feeds the OSM-hours branch
            p = dict(p, osm_evidence={"osm": om["osm"], "dist_m": om["dist_m"],
                                      "hours": om["tags"].get("opening_hours"),
                                      "fee": om["tags"].get("fee"), "name": om["tags"].get("name")})
        hours, legacy_hours, pv_hours, q_hours = build_hours(p, cat, arch, hours_web, policy, access,
                                                             web_item)
        price, pv_price, q_price = build_price(v, cat, arch, price_web, web_tickets, policy,
                                               pid in cluster and cluster[pid] in ("ba_na", "ngu_hanh_son"))
        tags = build_tags(p, cat)

        dur_src = p.get("dur_source")
        g = geo.get(pid) or {}
        kind = R.dwell_kind(cat, p["name"], arch)
        dwell = {**p["visit_min"], "unit": "min", "kind": kind, "v1": dict(p["visit_min"])}
        if dur_src == "human":
            pv_dwell = prov("user_review", "user")
        elif g.get("dur") == "ok":
            pv_dwell = prov("category_rule+user_ok", "user", confidence=0.6,
                            note="người dùng xác nhận ước lượng (geo review)")
        else:
            q25, q50, q75 = R.DWELL[kind]
            dwell.update(p25=q25, p50=q50, p75=q75)
            pv_dwell = prov(f"dwell_table_v2:{kind}", "inferred", confidence=0.4,
                            note="ƯỚC LƯỢNG theo loại điểm (thay rule v1); hiệu chỉnh lại từ log pilot")

        google_src = p.get("source") == "serpapi/google-maps"
        q = {k: p.get(k) for k in GOOGLE_FIELDS if google_src and p.get(k) not in (None, "", [])}
        q.update(q_hours)
        q.update(q_price)
        if google_src and q_hours.get("opening_hours"):
            # every-day Google hours (∩ road access window), used by poi_view
            # only under GOOGLE_POLICY=demo_phi_thuong_mai
            every = R.intersect_all(q_hours["opening_hours"])
            if every and access:
                every = R.intersect(every, access)
            if every:
                q["hours_open"] = R.fmt(every)[0].split(", ")

        osm = p.get("osm_evidence") or {}
        osm_id = osm.get("osm") if osm and osm_name_ok(p, osm) else None
        if om:
            osm_id = om["osm"]
            pop = dict(popularity.get(pid) or {})
            pop.setdefault("wikidata", om["tags"].get("wikidata"))
            popularity[pid] = pop
        if p.get("source") == "osm/overpass":
            osm_id = osm_id or p.get("osm_id") or p.get("poi_id")
        loc_src = {"serpapi/google-maps": "google_maps", "osm/overpass": "osm"}.get(p.get("source"), "manual")
        loc_pv = prov(loc_src, "open_data" if loc_src == "osm" else
                      ("agent_web" if loc_src == "manual" else "inferred"),
                      confidence=0.7 if loc_src == "osm" else 0.6,
                      note=None if loc_src == "osm" else (
                          "toạ độ gốc Google — cần đối chiếu OSM" if loc_src == "google_maps"
                          else "nhập thủ công (manual_pois.json / web) — cần đối chiếu OSM"))
        signature = bool(p.get("must_go")) or p["name"] in SIGNATURE_EXTRA
        pop = popularity.get(pid) or {}

        v.update({
            "data_version": DATA_VERSION,
            "name_vi": p["name"],
            "name_en": None,
            "ext_ids": {"osm": osm_id, "osm_match_m": osm.get("dist_m") if osm_id else None,
                        "overture": None, "wikidata": pop.get("wikidata")},
            "category": cat,
            "category_evidence": cat_ev[pid],
            "role": R.ROLE_OF[cat],
            "status": status,
            "status_reason": excl or rev,
            "zone": R.zone_of(p["lat"], p["lon"]),
            "cluster_id": cluster.get(pid),
            "alt_group": alt.get(pid),
            "hours": hours,
            "price": price,
            "tags": tags,
            "time_profile": R.TIME_PROFILE[cat],
            "dwell": dwell,
            "popularity": {"wikipedia_views_90d": pop.get("wikipedia_views_90d"),
                           "wikidata_sitelinks": pop.get("wikidata_sitelinks"),
                           "signature": signature},
            "description": {"text": None, "source": None, "license": None},
            "provenance": {
                "name": prov(loc_src, loc_pv["verified_by"], confidence=loc_pv["confidence"],
                             note=loc_pv["note"]),
                "location": loc_pv,
                "category": prov("rules_v2", "inferred",
                                 confidence=0.8 if cat_ev[pid][0].startswith("override") else 0.6,
                                 note=";".join(cat_ev[pid])),
                "hours": pv_hours,
                "price": pv_price,
                "dwell": pv_dwell,
                "tags": prov(p.get("smart_tag_source") or "rule_v1", "inferred", confidence=0.5),
                "v1_verified": {"verified_by_v1": p.get("verified_by"),
                                "verified_at_v1": p.get("verified_at"),
                                "mapped_to": "inferred"},
            },
            "valid_from": TODAY,
            "valid_to": None,
        })

        # ---- legacy fields the current app reads (policy-resolved) -------
        v["opening_hours"] = legacy_hours
        v["visit_min"] = {k: dwell[k] for k in ("p25", "p50", "p75")}
        st = dict(v.get("smart_tags") or {})
        v1_band = st.pop("price_band", None)
        st.pop("band_source", None)
        if st.get("band_verified") and v1_band and pv_price["verified_by"] == "user":
            price.setdefault("legacy_band_user", v1_band)
        pconf = pv_price["confidence"]
        lb = None
        if price.get("free_entry") and pconf >= LEGACY_MIN_CONF:
            v["free_entry"] = True
        elif price.get("legacy_band_web") and pconf >= 0.55:
            lb = price["legacy_band_web"]
        elif price.get("legacy_band_user") and price.get("typical_vnd") is None:
            lb = price["legacy_band_user"]
        elif price.get("typical_vnd") is not None and pconf >= (0.5 if pv_price["verified_by"] == "google_demo" else LEGACY_MIN_CONF):
            lb = R.legacy_band(price["typical_vnd"])
        if lb:
            st["price_band"] = lb
            st["band_source"] = pv_price["verified_by"]
        if v1_band and not lb:
            st["price_band_v1"] = v1_band       # kept for traceability, not read
        v["smart_tags"] = st
        if status == "excluded":
            v["verified"] = False
        if policy == "cach_ly":
            for k in ("rating", "ambience", "pros", "cons"):
                if google_src:
                    v[k] = None if k == "rating" else ([] if k in ("pros", "cons") else "")
        out_pois.append(v)
        rec, arch_fields = to_v21(v, p, pv_hours, legacy_hours, q)
        if pid in decisions:
            apply_decision(rec, decisions[pid])
        if pid in human:
            apply_human_verify(rec, human[pid])
        v21.append(rec)
        archive[pid] = arch_fields
        if q:
            quarantine[pid] = q

        if pid in v1_ids and R.V1_CAT_FALLBACK.get(p.get("cat")) != cat:
            changes.append({"poi_id": pid, "name": p["name"], "v1_cat": p.get("cat"),
                            "v2_category": cat, "evidence": ";".join(cat_ev[pid])})
        if status != "active":
            review_rows.append({"poi_id": pid, "name": p["name"], "status": status,
                                "reason": excl or rev, "category": cat})

    meta = {
        "snapshot": "danang-v2",
        "data_version": DATA_VERSION,
        "derived_from": "danang-v1",
        "fetched_at": v1.get("fetched_at"),
        "built_at": TODAY,
        "google_policy": "runtime (GOOGLE_POLICY env; pois.json is always clean)",
        "google_policy_default": runtime_policy,
        "source": "danang-v1 (serpapi/google-maps + osm + manual) re-labelled; see provenance",
        "sources": sorted({r["provenance"]["location"]["source"] for r in v21}),
        "count": len(v21),
        "count_by_status": dict(Counter(p["status"] for p in v21)),
        "count_by_category": dict(Counter(p["category"] for p in v21)),
        "count_by_zone": dict(Counter(p["zone"] for p in v21)),
        "applied_decisions": len(decisions), "applied_human_verify": len(human),
        "matrix": "matrix_ref.json -> danang-v1/matrix.json (v1 poi_ids only)",
        "count_new_pois": len(new_pois),
        "count_v1_pois": len(v1_ids),
        "count_by_price_tier": dict(Counter(str(r["price"]["tier"]) for r in v21)),
        "count_by_hours_kind": dict(Counter(r["hours"]["kind"] for r in v21)),
        "pois": v21,
    }
    _dump(os.path.join(out_dir, "pois.json"), meta)
    _dump(os.path.join(out_dir, "quarantine_google.json"),
          {"note": "Giá trị gốc Google (SerpAPI). KHÔNG dùng để train hay xuất production. "
                   "Chỉ BE.common.poi_view đọc file này khi GOOGLE_POLICY=demo_phi_thuong_mai.",
           "items": quarantine})
    _dump(os.path.join(out_dir, "archive_fields.json"),
          {"note": "Trường cũ (v1/v2.0) không còn dùng — chỉ để truy vết, không module nào đọc lúc chạy. "
                   "Giá trị gốc Google nằm ở quarantine_google.json, không ở đây.",
           "data_version": DATA_VERSION, "items": archive})
    if not os.path.exists(os.path.join(out_dir, "matrix.json")):
        # Q2: danang-v2 owns its matrix once WP7 builds it (expand_poi_matrix
        # --select stops); until then the v1 matrix is reused by reference.
        _dump(os.path.join(out_dir, "matrix_ref.json"),
              {"matrix_from": "../danang-v1/matrix.json",
               "reason": "v1 poi_ids reuse the v1 matrix (avoid a 26 MB copy)",
               "missing_ids_note": "POI mới (added_in=v2.0-p0b) và 173 POI v1 chưa có hàng ma trận — cần tính lại"})
    _csv(os.path.join(reports_dir, "08_new_pois.csv"),
         [{"poi_id": p["poi_id"], "name": p["name"], "category": p["category"], "zone": p["zone"],
           "cluster_id": p["cluster_id"], "requires_ticket_of": p["requires_ticket_of_name"],
           "hours": ", ".join(p["opening_hours"]), "hours_by": p["provenance"]["hours"]["verified_by"]}
          for p in out_pois if p.get("added_in")] +
         [{"poi_id": s["new"], "name": s["name"], "category": "SKIPPED_DUPLICATE",
           "zone": s["existing_name"]} for s in skipped_new],
         ["poi_id", "name", "category", "zone", "cluster_id", "requires_ticket_of", "hours", "hours_by"])

    write_exports(out_pois, exports_dir, {r["poi_id"]: r for r in v21})
    write_reports(out_pois, v1, quarantine, changes, review_rows, dups, reports_dir, policy,
                  {r["poi_id"]: r for r in v21})
    return meta


# --------------------------------------------------------------------------
# exports (always clean)
# --------------------------------------------------------------------------

FEATURE_COLS = [
    "poi_id", "name_vi", "category", "role", "status", "zone", "cluster_id", "alt_group",
    "lat", "lon", "indoor", "kid_friendly", "effort", "sun_exposure", "rain_cover",
    "time_of_day", "weather_sensitive", "archetype", "time_profile",
    "dwell_p25", "dwell_p50", "dwell_p75", "dwell_conf",
    "price_band", "price_min_vnd", "price_max_vnd", "price_basis", "price_conf",
    "free_entry", "hours_spans", "hours_conf", "hours_verified_by", "signature", "osm_id",
    "price_tier", "hours_kind", "prize_prior",            # v2.1 (WP12)
]


def _clean_value(prv):
    return prv and prv.get("verified_by") != "google_demo"


def write_exports(pois, exports_dir, v21_by_id=None):
    rows, weak = [], []
    v21_by_id = v21_by_id or {}
    for p in pois:
        pv = p["provenance"]
        r21 = v21_by_id.get(p["poi_id"]) or {}
        hours_ok, price_ok = _clean_value(pv["hours"]), _clean_value(pv["price"])
        safe_hours = p["hours"]["spans"] if hours_ok else p["hours"]["safe_windows"]
        rows.append({
            "poi_id": p["poi_id"], "name_vi": p["name_vi"], "category": p["category"],
            "role": p["role"], "status": p["status"], "zone": p["zone"],
            "cluster_id": p["cluster_id"], "alt_group": p["alt_group"],
            "lat": p["lat"], "lon": p["lon"],
            "indoor": p["tags"]["indoor"], "kid_friendly": p["tags"]["kid_friendly"],
            "effort": p["tags"]["effort"], "sun_exposure": p["tags"]["sun_exposure"],
            "rain_cover": p["tags"]["rain_cover"],
            "time_of_day": "|".join(p["tags"]["time_of_day"] or []),
            "weather_sensitive": p["tags"]["weather_sensitive"],
            "archetype": p["hours"]["archetype"], "time_profile": p["time_profile"],
            "dwell_p25": p["dwell"]["p25"], "dwell_p50": p["dwell"]["p50"],
            "dwell_p75": p["dwell"]["p75"], "dwell_conf": pv["dwell"]["confidence"],
            "price_band": p["price"]["band"] if price_ok else None,
            "price_min_vnd": p["price"]["min_vnd"] if price_ok else None,
            "price_max_vnd": p["price"]["max_vnd"] if price_ok else None,
            "price_basis": p["price"]["basis"],
            "price_conf": pv["price"]["confidence"] if price_ok else 0.0,
            "free_entry": p["price"]["free_entry"] if price_ok else None,
            "hours_spans": "|".join(safe_hours or []),
            "hours_conf": pv["hours"]["confidence"] if hours_ok else CONF["inferred"],
            "hours_verified_by": pv["hours"]["verified_by"] if hours_ok else "inferred",
            "signature": p["popularity"]["signature"], "osm_id": p["ext_ids"]["osm"],
            "price_tier": (r21.get("price") or {}).get("tier"),
            "hours_kind": (r21.get("hours") or {}).get("kind"),
            "prize_prior": (r21.get("popularity") or {}).get("prize_prior"),
        })
        ev = p["category_evidence"]
        name_only = R.classify_name_only(p["name_vi"])
        uses_type = any(e.startswith("type:") for e in ev[:1])
        conf = 0.9 if ev[0].startswith("override") else (
            0.8 if (name_only == p["category"] and any(e.startswith("type:") for e in ev)) else
            0.6 if name_only == p["category"] else 0.5 if uses_type else 0.3)
        weak.append({"poi_id": p["poi_id"], "text": p["name_vi"], "label": p["category"],
                     "label_name_only": name_only, "agree": name_only == p["category"],
                     "label_uses_google_type": uses_type, "label_conf": conf,
                     "status": p["status"]})
    _csv(os.path.join(exports_dir, "poi_features.csv"), rows, FEATURE_COLS)
    _csv(os.path.join(exports_dir, "poi_classifier_weak.csv"), weak,
         ["poi_id", "text", "label", "label_name_only", "agree", "label_uses_google_type",
          "label_conf", "status"])
    with open(os.path.join(exports_dir, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(EXPORT_README)


EXPORT_README = """# Exports `danang-v2` (training-safe)

Sinh bởi `BE/ml/data/migrate_v2.py`. **Không chứa trường gốc Google** (rating,
price_level, type, ambience, pros/cons, giờ/giá lấy từ Google) — bất kể chính sách
khi build snapshot. Giá trị nào chỉ có nguồn Google thì để trống và confidence thấp.

## poi_features.csv — đặc trưng POI cho ranker / candidate pruner / u(t)

| cột | ý nghĩa |
|---|---|
| category, role, zone | nhãn v2 (12 thể loại + lodging) |
| cluster_id, alt_group | cụm vé chung (ba_na, ngu_hanh_son) / nhóm thay thế (chỉ chọn 1) |
| indoor, effort, sun_exposure, rain_cover, time_of_day | tag suy luận (rule_v1), confidence 0.5 |
| archetype, time_profile | nhóm giờ + id đường cong u(t) (định nghĩa ở P1) |
| dwell_p25/p50/p75 | phút ở lại (ước lượng theo thể loại trừ khi `dwell_conf` >= 0.6) |
| price_band (re/vua/kha/cao), price_min/max_vnd, price_conf | chỉ nguồn sạch; trống nếu chỉ có Google |
| hours_spans, hours_conf, hours_verified_by | giờ mở mọi ngày từ nguồn sạch, nếu không có thì khung an toàn của nhóm giờ |
| signature | điểm tiêu biểu (danh sách must-go đã duyệt) |
| price_tier | v2.1: free / cheap / medium / expensive / included / trống (DATA_SPEC_v2_1) |
| hours_kind | v2.1: fixed (giờ có nguồn) / safe_window (khung an toàn theo nhóm) / unknown |
| prize_prior | v2.1: tín hiệu xếp hạng sạch 0–1 (thể loại + tiêu biểu + Wikidata/Wikipedia), thay rating Google |

## poi_classifier_weak.csv — nhãn yếu cho bộ phân loại POI (TF-IDF + LightGBM)

`label` = luật v2 (tên → loại Google → v1). `label_uses_google_type = true` nghĩa là
nhãn dựa vào loại Google: khi train sạch, bỏ các dòng này hoặc để cleanlab xử lý,
và ưu tiên dòng `label_conf >= 0.6`. Nhãn phải được người duyệt trước khi coi là gold.
"""


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def write_reports(pois, v1, quarantine, changes, review_rows, dups, reports_dir, policy,
                  v21_by_id=None):
    os.makedirs(reports_dir, exist_ok=True)
    _csv(os.path.join(reports_dir, "02_category_changes.csv"), changes,
         ["poi_id", "name", "v1_cat", "v2_category", "evidence"])
    _csv(os.path.join(reports_dir, "03_status_review.csv"), review_rows,
         ["poi_id", "name", "status", "reason", "category"])
    _csv(os.path.join(reports_dir, "04_duplicate_candidates.csv"), dups,
         ["a_id", "a_name", "b_id", "b_name", "dist_m", "name_ratio"])

    # archetype check against the (quarantined) Google every-day hours:
    # INTERNAL QA ONLY - measures how often our safe window is really open.
    arch_eval = defaultdict(lambda: {"n": 0, "inside": 0})
    for p in pois:
        raw = (quarantine.get(p["poi_id"]) or {}).get("opening_hours")
        safe = [s for w in p["hours"]["safe_windows"] for s in R.parse_element(w)]
        if not raw or not safe:
            continue
        every = R.intersect_all(raw)
        if not every:
            continue
        a = arch_eval[p["hours"]["archetype"]]
        a["n"] += 1
        a["inside"] += int(R.contains(every, safe))
    arch_rows = [{"archetype": k, "n_with_google_hours": v["n"], "safe_inside": v["inside"],
                  "share": round(v["inside"] / v["n"], 2) if v["n"] else None}
                 for k, v in sorted(arch_eval.items())]
    _csv(os.path.join(reports_dir, "05_archetype_vs_google.csv"), arch_rows,
         ["archetype", "n_with_google_hours", "safe_inside", "share"])

    ticket_rows = []
    for p in pois:
        if p["status"] == "excluded":
            continue
        if p["price"]["status"] in ("todo",) or (
                p["category"] in ("paid_attraction", "museum_indoor")
                and p["price"]["basis"] == "ticket"
                and not (p["price"]["ticket_vnd"] or p["price"]["free_entry"])
                and p["price"]["status"] != "known"):
            ticket_rows.append({"poi_id": p["poi_id"], "name": p["name"], "category": p["category"],
                                "zone": p["zone"], "current_note": p["price"]["note"],
                                "price_status": p["price"]["status"]})
    _csv(os.path.join(reports_dir, "07_ticket_checklist.csv"), ticket_rows,
         ["poi_id", "name", "category", "zone", "current_note", "price_status"])

    queue = verify_queue(pois, v21_by_id=v21_by_id)
    _csv(os.path.join(reports_dir, "11_verify_queue.csv"), queue,
         ["rank", "poi_id", "name", "category", "zone", "priority", "why", "hours_now",
          "hours_by", "price_now", "price_by", "maps_search"])
    write_queue_html(queue, os.path.join(reports_dir, "11_verify_queue.html"))

    summ = summary(pois, v1, quarantine, changes, dups, arch_rows, ticket_rows, policy)
    _dump(os.path.join(reports_dir, "01_migration_summary.json"), summ)


def verify_queue(pois, limit=150, v21_by_id=None):
    """Top POIs by importance x uncertainty, in v2.1 terms (hours.kind,
    price.tier) when `v21_by_id` is given. Signature POIs first (gate G3)."""
    weights = {"paid_attraction": 1.0, "museum_indoor": 0.9, "beach": 0.8, "viewpoint": 0.8,
               "religious": 0.5, "outdoor_landmark": 0.6, "night_market": 0.9,
               "day_market": 0.7, "restaurant": 0.6, "cafe": 0.4, "nightlife": 0.4,
               "wellness": 0.3}
    v21_by_id = v21_by_id or {}
    rows = []
    for p0 in pois:
        r21 = v21_by_id.get(p0["poi_id"])
        p = {**p0, "provenance": r21["provenance"], "status": r21["status"],
             "name": r21["name"]} if r21 else p0
        if p["status"] == "excluded" or p["role"] == "base":
            continue
        pv = p["provenance"]
        hc, pc = pv["hours"]["confidence"], pv["price"]["confidence"]
        imp = weights.get(p["category"], 0.3) + (0.8 if p["popularity"]["signature"] else 0)
        unc = 1 - min(hc, pc)
        if unc < 0.3:
            continue
        why = []
        if hc < 0.6:
            why.append(f"giờ {pv['hours']['verified_by']} {hc}")
        if pc < 0.6:
            why.append(f"giá {pv['price']['verified_by']} {pc}")
        if p["status"] == "review":
            why.append(f"review: {p['status_reason']}")
            imp += 0.3
        q = (p["name"] + " Đà Nẵng").replace(" ", "+")
        if r21:
            hours_now = (", ".join(r21["hours"]["open"]) or "—") + f" [{r21['hours']['kind']}]"
            price_now = str(r21["price"]["tier"])
        else:
            hours_now = ", ".join(p["hours"]["spans"]) or "—"
            price_now = (f"{p['price']['band']} {p['price']['min_vnd']}-{p['price']['max_vnd']}"
                         if p["price"]["band"] else p["price"]["status"])
        rows.append({"poi_id": p["poi_id"], "name": p["name"], "category": p["category"],
                     "zone": p["zone"], "priority": round(imp * unc, 3), "why": "; ".join(why),
                     "hours_now": hours_now,
                     "hours_by": pv["hours"]["verified_by"],
                     "price_now": price_now,
                     "price_by": pv["price"]["verified_by"],
                     "maps_search": f"https://www.google.com/maps/search/{q}"})
    rows.sort(key=lambda r: -r["priority"])
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
            f"<tr data-id='{r['poi_id']}'><td>{r['rank']}</td><td>{html.escape(r['name'])}</td>"
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
        f.write(head + "".join(body) + tail)


def summary(pois, v1, quarantine, changes, dups, arch_rows, ticket_rows, policy):
    def dist(field):
        return dict(Counter(p["provenance"][field]["verified_by"] for p in pois))

    active = [p for p in pois if p["status"] != "excluded"]
    zone_roles = defaultdict(Counter)
    for p in active:
        zone_roles[p["zone"]][p["role"]] += 1
    return {
        "built_at": TODAY, "google_policy": policy,
        "v1_count": len(v1["pois"]), "v1_meta_count": v1.get("count"), "v2_count": len(pois),
        "status": dict(Counter(p["status"] for p in pois)),
        "category": dict(Counter(p["category"] for p in pois)),
        "role": dict(Counter(p["role"] for p in pois)),
        "zone": dict(Counter(p["zone"] for p in pois)),
        "zone_roles": {z: dict(c) for z, c in zone_roles.items()},
        "clusters": dict(Counter(p["cluster_id"] for p in pois if p["cluster_id"])),
        "hours_verified_by": dist("hours"),
        "price_verified_by": dist("price"),
        "dwell_verified_by": dist("dwell"),
        "legacy_hours_nonempty": sum(1 for p in pois if p["opening_hours"]),
        "v1_hours_nonempty": sum(1 for p in v1["pois"] if p.get("opening_hours")),
        "legacy_price_band": sum(1 for p in pois if (p.get("smart_tags") or {}).get("price_band")),
        "legacy_free_entry": sum(1 for p in pois if p.get("free_entry")),
        "hours_conflict": sum(1 for p in pois if p["hours"]["conflict"]),
        "quarantined_pois": len(quarantine),
        "category_changes": len(changes),
        "duplicate_candidates": len(dups),
        "archetype_vs_google": arch_rows,
        "ticket_todo": len(ticket_rows),
        "osm_linked": sum(1 for p in pois if p["ext_ids"]["osm"]),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--v1", default=os.path.join("BE", "data", "snapshots", "danang-v1"))
    ap.add_argument("--out", default=os.path.join("BE", "data", "snapshots", "danang-v2"))
    ap.add_argument("--exports", default=os.path.join("BE", "data", "exports", "danang-v2"))
    ap.add_argument("--reports", default=os.path.join("reports", "p0"))
    ap.add_argument("--sources", default=os.path.join("BE", "data", "sources"))
    ap.add_argument("--google-policy", default=os.environ.get("GOOGLE_POLICY", DEFAULT_POLICY),
                    choices=POLICIES)
    a = ap.parse_args(argv)
    meta = migrate(a.v1, a.out, a.exports, a.reports, a.google_policy, a.sources)
    print(json.dumps({k: meta[k] for k in ("snapshot", "count", "google_policy",
                                            "count_by_status", "count_by_category",
                                            "count_by_zone")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
