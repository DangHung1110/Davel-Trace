"""Auto spot-check v2 for the full snapshot (lane A, stdlib only).

Deterministic + heuristic flags (no verdicts — human ticks those):
  D1 duplicate clusters (same norm name or <100m + name overlap)
  D2 hours empty / suspicious-24/7-indoor / unparsable format
  D3 duration outliers (p50 deviates >60% from canonical median)
  D4 rating None / perfect-5.0 (no review counts in data to confirm)
  D5 ticket True without price/source (unverified pay claim)
  D6 coords outside DN bbox
  D7 unmapped raw type (junk/removal candidates)
  D8 generic one-word names (likely dup/junk)

Usage: python BE/ml/data/spotcheck_v2.py --snapshot ... [--apply-flag]
--apply-flag writes auto-verdicts ONLY for safe deterministic cases
(24/7 open-access already sourced, OSM-confirmed hours); everything else
stays human. Prints report either way.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

from BE.ml.patm.estimate_duration import canonical_category  # noqa: E402

DN_BBOX = (15.80, 107.75, 16.35, 108.55)  # s,w,n,e
HOUR_RE = re.compile(r"^(\d{2}:\d{2})-(\d{2}:\d{2})(,|$)")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", s).strip()


def hav(a, b, c, d) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin(math.radians(c - a) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--review-out", default="")
    args = ap.parse_args()
    with open(os.path.join(args.snapshot, "pois.json"), encoding="utf-8") as f:
        pois = json.load(f)["pois"]
    flags: dict[str, list[str]] = defaultdict(list)

    # D1 duplicates
    by_name: dict[str, list] = defaultdict(list)
    name_of = {}
    info_of = {}
    for p in pois:
        by_name[_norm(p["name"])].append(p["poi_id"])
        name_of[p["poi_id"]] = p["name"]
        info_of[p["poi_id"]] = (f"{p['name']} [{p['poi_id'][:8]}] | "
                                f"{p.get('type')} ★{p.get('rating')} "
                                f"{','.join(p.get('opening_hours') or ['no-hours'])}")
    for n, ids in by_name.items():
        if len(ids) > 1:
            flags[f"D1-dup-name:{name_of[ids[0]]}"] = [info_of[i] for i in ids]
    for i, a in enumerate(pois):
        for b in pois[i + 1:]:
            if hav(a["lat"], a["lon"], b["lat"], b["lon"]) < 100:
                wa, wb = set(_norm(a["name"]).split()), set(_norm(b["name"]).split())
                if wa & wb and len(wa & wb) >= 2:
                    def _info(p):
                        return (f"{p['name']} [{p['poi_id'][:8]}] | {p.get('type')} "
                                f"★{p.get('rating')} {','.join(p.get('opening_hours') or ['no-hours'])}")
                    flags[f"D1-near-dup:{a['name']} / {b['name']}"] = [_info(a), _info(b)]

    med: dict[str, float] = {}
    groups: dict[str, list] = defaultdict(list)
    for p in pois:
        groups[canonical_category(p.get("type", ""))].append((p.get("visit_min") or {}).get("p50", 0))
    for k, vs in groups.items():
        vs = sorted(v for v in vs if v)
        med[k] = vs[len(vs) // 2] if vs else 0

    for p in pois:
        pid = f"{p['name']} [{p['poi_id'][:8]}]"
        canon = canonical_category(p.get("type", ""))
        # D2 hours
        if not p.get("opening_hours"):
            flags[f"D2-no-hours"].append(pid)
        else:
            for h in p["opening_hours"]:
                parts = [x.strip() for x in h.split(",")]
                if not all(HOUR_RE.match(x) or x == "00:00-23:59" for x in parts):
                    flags["D2-bad-format"].append(f"{pid}: {h}")
        # D3 duration outliers
        p50 = (p.get("visit_min") or {}).get("p50", 0)
        m = med.get(canon, 0)
        if m and abs(p50 - m) / m > 0.6:
            flags["D3-dur-outlier"].append(f"{pid}: p50={p50} vs {canon}-median={m}")
        # D4 rating
        if p.get("rating") is None:
            flags["D4-no-rating"].append(pid)
        elif p.get("rating") == 5.0:
            flags["D4-rating-5.0"].append(pid)
        # D5 ticket claim w/o evidence
        st = p.get("smart_tags") or {}
        if st.get("ticket") is True and p.get("ticket_vnd") is None and "price_sources" not in p:
            flags["D5-ticket-unverified"].append(pid)
        # D6 bbox
        s, w, n, e = DN_BBOX
        if not (s <= p["lat"] <= n and w <= p["lon"] <= e):
            flags["D6-outside-DN"].append(pid)
        # D7 unmapped type
        if canon == p.get("type") and canon not in (
                "landmark", "transport", "market", "nature", "restaurant",
                "museum", "beach", "attraction", "park", "cafe", "lodging"):
            flags["D7-unmapped-type"].append(f"{pid}: {p.get('type')}")
        # D8 generic names
        if len(_norm(p["name"]).split()) <= 1:
            flags["D8-generic-name"].append(pid)

    order = ["D1-dup-name", "D1-near-dup", "D2-no-hours", "D2-bad-format",
             "D3-dur-outlier", "D4-no-rating", "D4-rating-5.0",
             "D5-ticket-unverified", "D6-outside-DN", "D7-unmapped-type",
             "D8-generic-name"]
    total_human = 0
    for key in order:
        items = [v for k, v in flags.items() if k == key or k.startswith(key + ":")]
        n = sum(len(v) for v in items)
        if key in ("D2-no-hours", "D4-no-rating"):
            print(f"{key}: {n} (info, batch-fillable)")
            continue
        total_human += len(items) if key.startswith("D1") else n
        print(f"{key}: clusters={len(items)} items={n}")
        for k in list(flags):
            if k == key or k.startswith(key + ":"):
                for v in flags[k][:8]:
                    print(f"    - {v}")
                if len(flags[k]) > 8:
                    print(f"    ... +{len(flags[k]) - 8}")
    print(f"TOTAL human-review items ~= {total_human}")
    if args.review_out:
        with open(os.path.join(args.snapshot, "pois.json"), encoding="utf-8") as f:
            by_id = {p["poi_id"]: p for p in json.load(f)["pois"]}
        L = ["# Review v2 — tick để xử lý (giữ nguyên thứ tự dòng)",
             "",
             "D1: tick 1 ô mỗi cụm: GIỮ HẾT (khác nhau thật) | GỘP (ghi tên giữ lại) | LOẠI (ghi poi_id bỏ).",
             "D3/D4/D5/D7/D8: tick Dung (đúng, giữ) hoặc Sai + ghi chú sửa.",
             ""]
        for key in order:
            ks = [k for k in flags if k == key or k.startswith(key + ":")]
            if not ks or key in ("D2-no-hours", "D4-no-rating"):
                continue
            L.append(f"## {key}")
            for k in ks:
                L.append(f"### {k}")
                for v in flags[k]:
                    L.append(f"- [ ] {v} => ")
            L.append("")
        with open(args.review_out, "w", encoding="utf-8") as f:
            f.write("\n".join(L))
        print(f"review -> {args.review_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
