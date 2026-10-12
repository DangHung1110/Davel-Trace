"""Fill price_band from SerpApi search-payload prices (lane A, no quota).

Search payloads carry `price` strings ("100-200 N ₫" = nghìn đồng,
"11 US$", "1-400.000 ₫"). Upper bound -> band: cheap <100k,
medium 100-500k, expensive >500k. Joins by place_id; only fills null
bands (web-verified prices win). Also fills price_level 1-3.

Usage: python BE/ml/data/price_from_raw.py --snapshot ... --raw BE/data/raw-round2 [--raw data/snapshots/danang-full-tmp]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

USD = 25000


def parse_upper_vnd(s: str) -> int | None:
    """Upper bound of a price string in VND, or None."""
    if not s:
        return None
    t = s.replace("\xa0", " ").replace("–", "-").replace("—", "-")
    nums = [float(x.replace(".", "").replace(",", "."))
            for x in re.findall(r"[\d.,]+", t)]
    if not nums:
        return None
    up = nums[-1]
    low = t.lower()
    if "us$" in low or "usd" in low or "$" in low:
        return int(up * USD)
    mult = 1000 if ("n " in low or " nghìn" in low or re.search(r"\bn\b", low) or up < 1000) else 1
    # "1-100.000 ₫": dotted thousands; bare "100-200" with N = thousands
    if up < 1000 and ("₫" in low or "d" in low.split() or "vnd" in low):
        mult = 1000
    return int(up * mult)


def band(vnd: int) -> str:
    return "cheap" if vnd < 100000 else ("medium" if vnd <= 500000 else "expensive")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--raw", action="append", default=[])
    args = ap.parse_args()
    found: dict[str, tuple[int, str]] = {}
    for raw in args.raw:
        for root, _, fs in os.walk(raw):
            for f in fs:
                if not f.endswith(".json") or f == "quota.json":
                    continue
                try:
                    d = json.load(open(os.path.join(root, f), encoding="utf-8"))
                except Exception:  # noqa: BLE001 - partial/corrupt cache
                    continue
                items = d if isinstance(d, list) else d.get("local_results", [])
                if isinstance(items, dict):
                    items = items.get("local_results", [])
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    pid = it.get("place_id") or it.get("data_id")
                    v = parse_upper_vnd(str(it.get("price") or ""))
                    if pid and v and pid not in found:
                        found[pid] = (v, str(it.get("price")))
    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    n = 0
    for p in data["pois"]:
        st = p.get("smart_tags") or {}
        if p["poi_id"] in found and st.get("price_band") is None:
            v, raw = found[p["poi_id"]]
            st["price_band"] = band(v)
            st["ticket"] = True if st.get("ticket") is None else st["ticket"]
            p["smart_tags"] = st
            p["price_note"] = f"~{v:,}đ (payload: {raw})".replace(",", ".")
            p["price_level"] = 1 if v < 100000 else (2 if v <= 500000 else 3)
            n += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"payload prices: {len(found)} items, filled {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
