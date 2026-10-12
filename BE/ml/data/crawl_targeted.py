"""Targeted SerpApi crawl, round 2 (lane A, stdlib only).

14 queries for the missing groups (spiritual, Ba Na, cruise, diving,
hotels, spa, night markets, specialties, museums). Anti-junk:
bbox filter, dedup vs snapshot (place_id AND 150m+name overlap),
prune REMOVALS denylist, cafe freeze (new cafes need rating>=4.5),
food types need rating>=4.0 unless specialty keywords.
New POIs get full enrich (duration/intensity/ws/tags/cat), verified=false.

Key: SERPAPI_KEY_2 (fresh 250/month). Quota guard 240, own raw dir.

Usage: python BE/ml/data/crawl_targeted.py --snapshot BE/data/snapshots/danang-v1 --raw BE/data/raw-round2
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sys
import unicodedata

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

from BE.ml.data.fetch_serpapi import (  # noqa: E402
    DN_BBOX, QuotaTracker, _load_dotenv, cached_or_fetch, normalize,
    raw_path)
from BE.ml.data.prune_snapshot import REMOVALS, EXACT_KEYS  # noqa: E402
from BE.ml.patm.estimate_duration import canonical_category, enrich_poi  # noqa: E402

QUERIES = [
    "chùa Linh Ứng Đà Nẵng", "nhà thờ Đà Nẵng", "chùa Đà Nẵng",
    "Bà Nà Hills", "du thuyền sông Hàn", "lặn ngắm san hô Sơn Trà",
    "khách sạn view biển Đà Nẵng", "resort Đà Nẵng", "spa massage Đà Nẵng",
    "chợ đêm Đà Nẵng", "bảo tàng Đà Nẵng", "quán mì Quảng Đà Nẵng",
    "hải sản Đà Nẵng", "đặc sản Đà Nẵng",
]
SPECIALTY = ("mi quang", "my quang", "banh xeo", "hai san", "com ga", "cao lau",
             "bun cha ca", "banh trang", "che ")

# Round-3 grid: more of the missing groups per district (diminishing
# returns expected — SerpApi repeats top results across queries).
GRID_CATS = ["khách sạn", "spa", "quán bar", "chùa", "khu du lịch"]
GRID_DISTRICTS = ["Hải Châu", "Sơn Trà", "Ngũ Hành Sơn", "Liên Chiểu",
                  "Thanh Khê"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def hav(a, b, c, d) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin(math.radians(c - a) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def junk_reason(name: str) -> str | None:
    n = _norm(name)
    return next((REMOVALS[k] for k in REMOVALS
                 if (n == k if k in EXACT_KEYS else k in n)), None)


def keep_item(name: str, cats: list, rating, query: str) -> tuple[bool, str]:
    """Anti-junk gate. Returns (keep, reason)."""
    if junk_reason(name):
        return False, "denylist"
    canon = canonical_category(cats[0] if cats else "")
    r = rating
    if canon == "cafe" and not (r is not None and r >= 4.5):
        return False, "cafe-freeze"
    if canon == "restaurant":
        if r is None or r < 4.0:
            if not any(k in _norm(name) for k in SPECIALTY):
                return False, "low-food-no-specialty"
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--raw", required=True)
    args = ap.parse_args()
    _load_dotenv("BE/.env")
    key = os.environ.get("SERPAPI_KEY_2", "")
    if not key:
        raise SystemExit("SERPAPI_KEY_2 missing in BE/.env")
    quota = QuotaTracker(args.raw)
    snap_path = os.path.join(args.snapshot, "pois.json")
    with open(snap_path, encoding="utf-8") as f:
        data = json.load(f)
    by_id = {p["poi_id"]: p for p in data["pois"]}
    stats = {"queries": 0, "items": 0, "new": 0, "dup_id": 0,
             "dup_near": 0, "junk": 0, "outside": 0}
    junk_names: list[str] = []
    queries = list(QUERIES) + [f"{c} {d}" for c in GRID_CATS
                               for d in GRID_DISTRICTS]
    for q in queries:
        params = {"engine": "google_maps", "type": "search",
                  "q": q, "hl": "vi", "gl": "vn"}
        payload = cached_or_fetch(raw_path(args.raw, "search2", q),
                                  params, key, quota, f"search2: {q}")
        stats["queries"] += 1
        for item in payload.get("local_results", []):
            pid = item.get("place_id") or item.get("data_id")
            if not pid:
                continue
            stats["items"] += 1
            gps = item.get("gps_coordinates") or {}
            try:
                la, lo = float(gps.get("latitude")), float(gps.get("longitude"))
            except (TypeError, ValueError):
                continue
            s, w, n, e = DN_BBOX
            if not (s <= la <= n and w <= lo <= e):
                stats["outside"] += 1
                continue
            if pid in by_id:
                stats["dup_id"] += 1
                continue
            name = item.get("title", "")
            cats = item.get("types") or item.get("categories") or []
            ok, why = keep_item(name, cats, item.get("rating"), q)
            if not ok:
                stats["junk"] += 1
                junk_names.append(f"{name} ({why})")
                continue
            hit = None
            wn = set(_norm(name).split())
            for p in data["pois"]:
                if hav(la, lo, p["lat"], p["lon"]) < 150:
                    wo = set(_norm(p["name"]).split())
                    if wn & wo and len(wn & wo) >= 2:
                        hit = p["name"]
                        break
            if hit:
                stats["dup_near"] += 1
                continue
            poi = normalize(pid, item)
            poi["crawl_query"] = q
            enrich_poi(poi)
            canon = canonical_category(poi.get("type", ""))
            from BE.ml.data.enrich_snapshot import INTENSITY_DEFAULT, WS_DEFAULT  # noqa
            poi["intensity"] = INTENSITY_DEFAULT.get(canon, 2)
            poi["intensity_source"] = "canonical_rule"
            poi["weather_sensitive"] = WS_DEFAULT.get(canon, False)
            poi["ws_source"] = "canonical_rule"
            poi["io_label"] = None
            from BE.ml.data.enrich_tags import tag_poi  # noqa
            t, src = tag_poi(poi)
            poi["smart_tags"] = t
            poi["smart_tag_source"] = src
            poi["cat"] = canon
            data["pois"].append(poi)
            by_id[pid] = poi
            stats["new"] += 1
    data["count"] = len(data["pois"])
    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(json.dumps(stats, ensure_ascii=False))
    print(f"total {len(data['pois'])}")
    for j in junk_names[:20]:
        print("  junk:", j)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
