"""Add missing OSM POIs into the snapshot (lane A, stdlib only).

Candidates: OSM elements with tourist categories, >150m from every snapshot
POI, name present. Excludes boarding houses ("nhà trọ"), Lăng Cô leak
(Huế, not ĐN), info offices. Hotels only with stars=* or resort (unrated
hotels need SerpApi ratings first — recorded, not added).

New POIs get: poi_id osm:{type}/{id}, visit_min via estimate_duration,
intensity/ws/io via enrich_snapshot rules, smart_tags via enrich_tags,
verified=false, source=osm/overpass. Idempotent (skips osm: ids present).

Usage: python BE/ml/data/osm_add.py --snapshot ... --osm C:/tmp/osm/danang.json --check|--apply
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import sys
import unicodedata

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

from BE.ml.patm.estimate_duration import canonical_category, enrich_poi  # noqa: E402

DROP_NAME = ("nha tro", "lang co", "post office", "apartment",
             # bbox leak: Hội An / Điện Bàn / Huế side
             "hoi an", "dien ban", "cua dai", "suoi voi",
             # offices / junk / stadiums (not visitable attractions)
             "le tan", "fpt", "saturday option")
KEEP = {"hotel", "motel", "resort", "viewpoint", "museum", "gallery",
        "attraction", "theme_park", "gift", "souvenir", "marketplace",
        "place_of_worship", "church", "pagoda", "beach", "peak",
        "cave_entrance", "waterfall", "spring", "memorial", "monument",
        "park", "zoo"}
RADIUS_M = 150.0

# OSM tag -> Vietnamese raw type (feeds canonical_category downstream)
VI_TYPE = {
    "hotel": "Khách sạn", "motel": "Khách sạn", "resort": "Khu nghỉ dưỡng",
    "hostel": "Nhà nghỉ", "guest_house": "Nhà nghỉ",
    "viewpoint": "Điểm ngắm cảnh", "museum": "Bảo tàng", "gallery": "Phòng trưng bày",
    "attraction": "Điểm thu hút khách du lịch", "theme_park": "Công viên giải trí",
    "gift": "Cửa hàng quà lưu niệm", "souvenir": "Cửa hàng quà lưu niệm",
    "marketplace": "Chợ", "place_of_worship": "Cơ sở thờ tự",
    "church": "Nhà thờ", "pagoda": "Chùa",
    "beach": "Bãi biển", "peak": "Đỉnh núi", "cave_entrance": "Hang động",
    "waterfall": "Thác nước", "spring": "Suối", "memorial": "Đài tưởng niệm",
    "monument": "Tượng đài", "stadium": "Sân vận động", "park": "Công viên",
    "zoo": "Vườn thú",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def hav(a, b, c, d) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin(math.radians(c - a) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def el_latlon(el: dict):
    if el.get("type") == "node":
        return el.get("lat"), el.get("lon")
    c = el.get("center") or {}
    return c.get("lat"), c.get("lon")


def ocategory(el: dict) -> str:
    t = el.get("tags") or {}
    return t.get("tourism") or t.get("amenity") or t.get("leisure") or t.get("natural") or t.get("historic") or t.get("shop") or "?"


def candidates(pois: list[dict], elements: list[dict]):
    have = {(p["lat"], p["lon"]) for p in pois}
    have_ids = {p["poi_id"] for p in pois}
    out, skip_hotel = [], 0
    for el in elements:
        la, lo = el_latlon(el)
        tags = el.get("tags") or {}
        name = tags.get("name")
        if la is None or not name:
            continue
        c = ocategory(el)
        if c not in KEEP:
            continue
        nm = _norm(name)
        if any(k in nm for k in DROP_NAME):
            continue
        if c in ("hotel", "motel", "hostel", "guest_house") and c != "resort" \
                and "stars" not in tags:
            skip_hotel += 1
            continue
        if min(hav(la, lo, a, b) for a, b in have) <= RADIUS_M:
            continue
        pid = f"osm:{el.get('type')}/{el.get('id')}"
        if pid in have_ids:
            continue
        out.append((el, c, la, lo, name, tags))
    return out, skip_hotel


def osm_hours_to_schema(raw: str) -> tuple[list[str], str]:
    """Convert OSM opening_hours ('Mo-Fr 08:00-18:00; Sa 09:00-12:00') to
    schema ['08:00-18:00', ...] (day info kept in note). Unparseable ->
    ([], raw) so the caller stores it as evidence only."""
    times = re.findall(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})", raw or "")
    seen = list(dict.fromkeys(f"{a}-{b}" for a, b in times))
    if seen and re.match(r"^[\w\s,;\-:+]+$", raw or ""):
        return seen, raw
    return [], raw


def to_poi(el, c, la, lo, name, tags) -> dict:
    from BE.ml.data.enrich_snapshot import INTENSITY_DEFAULT, WS_DEFAULT, AUDIT_WS  # noqa
    oh, oh_raw = osm_hours_to_schema((tags or {}).get("opening_hours", ""))
    p = {"poi_id": f"osm:{el.get('type')}/{el.get('id')}", "name": name,
         "type": VI_TYPE.get(c, c), "lat": la, "lon": lo,
         "opening_hours": oh,
         "hours_source": "osm" if oh else "",
         "price_level": 2, "fee": 0, "rating": None,
         "tags": [VI_TYPE.get(c, c)], "source": "osm/overpass",
         "fetched_at": datetime.date.today().isoformat(), "verified": False}
    enrich_poi(p)
    canon = canonical_category(p["type"])
    p["intensity"] = INTENSITY_DEFAULT.get(canon, 2)
    p["intensity_source"] = "canonical_rule"
    p["weather_sensitive"] = WS_DEFAULT.get(canon, False)
    p["ws_source"] = "canonical_rule"
    p["io_label"] = None
    from BE.ml.data.enrich_tags import tag_poi  # noqa
    t, src = tag_poi(p)
    p["smart_tags"] = t
    p["smart_tag_source"] = src
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    with open(args.osm, encoding="utf-8") as f:
        elements = json.load(f).get("elements", [])
    cand, skip_hotel = candidates(data["pois"], elements)
    print(f"snapshot={len(data['pois'])} candidates={len(cand)} "
          f"(unrated hotels skipped={skip_hotel})")
    if args.check:
        from collections import Counter
        print(Counter(ocategory(e) for e, *_ in cand).most_common(15))
        for el, c, la, lo, name, tags in cand[:50]:
            print(f"  + [{c}] {name}")
        return 0
    if args.apply:
        for tup in cand:
            data["pois"].append(to_poi(*tup))
        data["count"] = len(data["pois"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"added {len(cand)} -> total {len(data['pois'])}")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
