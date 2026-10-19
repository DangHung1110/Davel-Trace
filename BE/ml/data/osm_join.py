"""Join OSM tags (fee, opening_hours) into snapshot by proximity (lane A).

Matches each POI to the nearest OSM element within RADIUS_M (haversine).
--check reports coverage + conflicts only. --apply fills opening_hours
ONLY when empty (+hours_source osm) and records osm_evidence on every
match; never overwrites crawl hours. OSM fee cross-checks ticket flags
(report only — ticket verdicts stay human/rule-driven).

Usage (repo root, native paths on Windows):
  python BE/ml/data/osm_join.py --snapshot BE/data/snapshots/danang-v1 --osm C:/tmp/osm/danang.json --check
  python BE/ml/data/osm_join.py --snapshot BE/data/snapshots/danang-v1 --osm C:/tmp/osm/danang.json --apply
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

RADIUS_M = 150.0

# Open-access outdoor POIs have no gate: 24/7 is factual, not a guess.
# Tight on purpose — caves/parks/night markets can be gated, skip them.
OPEN24_KEYS = (
    "bai bien", "public beach", "beach access",
    "viewpoint", "mui nghe", "dinh ban co", "deo hai van", "ban dao",
)
OPEN24_CANON = ("beach",)


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def el_latlon(el: dict):
    if el.get("type") == "node":
        return el.get("lat"), el.get("lon")
    c = el.get("center") or {}
    return c.get("lat"), c.get("lon")


def match(pois: list[dict], elements: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in pois:
        best, best_d = None, RADIUS_M
        for el in elements:
            la, lo = el_latlon(el)
            if la is None or lo is None:
                continue
            d = haversine_m(p["lat"], p["lon"], la, lo)
            if d < best_d:
                best, best_d = el, d
        if best is not None:
            tags = best.get("tags", {})
            out[p["poi_id"]] = {
                "osm": f"{best.get('type')}/{best.get('id')}",
                "dist_m": round(best_d, 1),
                "fee": tags.get("fee"),
                "hours": tags.get("opening_hours"),
                "name": tags.get("name"),
            }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    ppath = os.path.join(args.snapshot, "pois.json")
    with open(ppath, encoding="utf-8") as f:
        data = json.load(f)
    with open(args.osm, encoding="utf-8") as f:
        elements = json.load(f).get("elements", [])
    m = match(data["pois"], elements)
    print(f"pois={len(data['pois'])} matched={len(m)} "
          f"with_hours={sum(1 for v in m.values() if v['hours'])} "
          f"with_fee={sum(1 for v in m.values() if v['fee'])}")
    if args.check:
        fillable = sum(1 for p in data["pois"]
                       if not p.get("opening_hours")
                       and (m.get(p["poi_id"]) or {}).get("hours"))
        agree = disagree = 0
        for p in data["pois"]:
            v = m.get(p["poi_id"])
            if not v or not v["fee"]:
                continue
            t = (p.get("smart_tags") or {}).get("ticket")
            osm_paid = v["fee"] == "yes"
            if t is None:
                continue
            if bool(t) == osm_paid:
                agree += 1
            else:
                disagree += 1
                if disagree <= 10:
                    print(f"  fee-conflict: {p['name']} rule={t} osm={v['fee']}")
        print(f"hours_fillable={fillable} fee_agree={agree} "
              f"fee_disagree={disagree}")
        return 0
    if args.apply:
        import unicodedata

        def _norm(s):
            s = unicodedata.normalize("NFD", str(s or "").lower())
            return "".join(c for c in s
                           if unicodedata.category(c) != "Mn").replace("đ", "d")

        from BE.ml.patm.estimate_duration import canonical_category
        filled = open24 = 0
        for p in data["pois"]:
            v = m.get(p["poi_id"])
            if v:
                p["osm_evidence"] = v
            if not p.get("opening_hours") and v and v["hours"]:
                p["opening_hours"] = [v["hours"]]
                p["hours_source"] = "osm"
                filled += 1
            if not p.get("opening_hours"):
                nm = _norm(p.get("name", ""))
                if (canonical_category(p.get("type", "")) in OPEN24_CANON
                        or any(k in nm for k in OPEN24_KEYS)):
                    p["opening_hours"] = ["00:00-23:59"]
                    p["hours_source"] = "rule_open_access"
                    open24 += 1
        with open(ppath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"matched {len(m)}, hours_filled osm={filled} "
              f"open24={open24} -> {ppath}")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
