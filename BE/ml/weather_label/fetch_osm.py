"""OSM fetch via Overpass (T063-M4CODE, lane A). Tags+geometry, local cache.

Raw JSON stays in TEMP (never committed). Areas: Da Nang bbox +
Hoi An (cheap 2nd VN site for generalization).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

API = "https://overpass-api.de/api/interpreter"
MIRROR = "https://overpass.kumi.systems/api/interpreter"
DN_BBOX = (15.9, 107.9, 16.25, 108.45)  # s,w,n,e
HOIAN_BBOX = (15.85, 108.28, 15.93, 108.37)

FILTERS = [  # node-only: light; ways fetched later for shortlisted POIs
    'node["tourism"]',
    'node["leisure"~"park|garden|beach|stadium|water_park|playground"]',
    'node["amenity"~"restaurant|cafe|museum|marketplace|place_of_worship|food_court"]',
    'node["historic"]',
    'node["shop"="mall"]',
]


def query(bbox: tuple[float, float, float, float]) -> str:
    s, w, n, e = bbox
    body = "\n  ".join(f"{f}({s},{w},{n},{e});" for f in FILTERS)
    return f"[out:json][timeout:180];\n(\n  {body}\n);\nout center tags;"


def fetch(bbox: tuple[float, float, float, float], out_path: str,
          timeout: int = 200) -> dict:
    data = urllib.parse.urlencode({"data": query(bbox)}).encode()
    last_err: Exception | None = None
    for base in (API, MIRROR):
        req = urllib.request.Request(
            base, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": "Davel-Trace/research (T063)"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = json.load(r)
            break
        except Exception as e:  # noqa: BLE001 - try mirror, else report
            print(f"{base} failed: {e}")
            last_err = e
            payload = {}
    else:
        raise RuntimeError(f"all Overpass endpoints failed: {last_err}")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    els = payload.get("elements", [])
    print(f"fetched {len(els)} elements -> {out_path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T063 OSM fetch")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--sites", default="danang,hoian")
    args = ap.parse_args(argv)
    out_dir = args.out_dir or os.path.join(
        os.environ.get("TEMP", "/tmp"), "opencode", "osm")
    for site, bbox in (("danang", DN_BBOX), ("hoian", HOIAN_BBOX)):
        if site not in args.sites.split(","):
            continue
        try:
            fetch(bbox, os.path.join(out_dir, f"{site}.json"))
        except Exception as e:  # noqa: BLE001 - report, continue other site
            print(f"FAILED {site}: {e}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
