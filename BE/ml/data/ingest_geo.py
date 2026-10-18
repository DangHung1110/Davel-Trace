"""Ingest geo_answers.json into snapshot (lane A).

Explicit per-POI table from user notes (auditable, no guessing):
- parking ("vé xe/giữ xe/đỗ xe") -> parking_note, entry ticket stays False
- durations with explicit minutes -> visit_min + dur_source human/medium
- rating corrections, hours fills, ticket flips, drops as noted.
Unmatched rows print and skip.

Usage: python BE/ml/data/ingest_geo.py --snapshot ... [--apply]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

PARKING = "xe: thường có phí giữ xe/đỗ xe (vé xe, không phải vé vào cửa)"

DUR = {  # poi_id: (p50, note)
    "ChIJD4Ge5WQZQjERW-0GhLbS310": (75, "user: đi dạo 60-90p"),
    "ChIJZSAyL0YfQjERMP2R9yBDRwY": (110, "user: đi dạo 100-120p"),
    "ChIJGSKUUwCLQTERr0Je7WP5Xqc": (75, "user: đi dạo 60-90p"),
    "osm:node/4122433690": (240, "user: Núi Bà Nà đi từ sáng tới chiều/tối"),
}
HOURS = {  # poi_id: ([hours], source-note)
    "ChIJGSKUUwCLQTERr0Je7WP5Xqc": (["06:00-23:30"], "user: mở 6:00-23:30"),
}
RATING = {  # poi_id: (rating, note)
    "ChIJZSAyL0YfQjERMP2R9yBDRwY": (3.8, "user: 3.8 sao"),
    "ChIJT1zm9U8NQjERQf5DsBriCgc": (4.1, "user: 4.1 sao; vào cửa miễn phí, liên hệ BQL Sơn Trà xác nhận phí đỗ xe"),
}
TICKET = {  # poi_id: (ticket_bool_or_None, note)
    "ChIJe8ah9rsZQjER6VQTZMzcGTw": (True, "user: hồ bơi có phí vào"),
    "ChIJZSAyL0YfQjERMP2R9yBDRwY": (None, "user: vé chưa rõ, có thể có"),
}
ACCESS = {  # poi_id: note
    "ChIJGSKUUwCLQTERr0Je7WP5Xqc": "user: đường vào có gờ cao, nguy hiểm xe gầm thấp",
}
PRICE = {  # poi_id: (band, note)
    "ChIJp91wYRgZQjER9Yry1HWPhW8": ("medium", "user: SAY Beer ~100-300k/người"),
    "ChIJH1TU7PsYQjER-jhAtZLdLMc": ("medium", "user: CẬU CẢ 100-600k/người"),
}
DROP_NAMES = ("Núi Đồng Đen", "Công Viên Cây Xanh")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    P = {p["poi_id"]: p for p in data["pois"]}
    ans = json.load(open(os.path.join(args.snapshot, "geo_answers.json"),
                         encoding="utf-8"))
    n_park = n_dupe = 0
    for x in ans:
        pid = x.get("poi_id")
        p = P.get(pid)
        if not p:
            continue
        note = (x.get("note") or "").lower()
        if any(k in note for k in ("vé xe", "giữ xe", "đỗ xe", "bãi đỗ", "vé giữ")):
            if "parking_note" not in p:
                n_park += 1
            if args.apply:
                p["parking_note"] = "user: " + (x.get("note") or "").strip()
    if args.apply:
        for pid, (p50, note) in DUR.items():
            if pid in P:
                P[pid]["visit_min"] = {"p25": round(p50 * 0.7),
                                       "p50": p50, "p75": round(p50 * 1.4)}
                P[pid]["dur_source"] = "human"
                P[pid]["dur_note"] = note
        for pid, (hrs, note) in HOURS.items():
            if pid in P and not P[pid].get("opening_hours"):
                P[pid]["opening_hours"] = hrs
                P[pid]["hours_source"] = "user-verify"
                P[pid]["hours_note"] = note
        for pid, (r, note) in RATING.items():
            if pid in P:
                P[pid]["rating"] = r
                P[pid]["rating_note"] = note
        for pid, (t, note) in TICKET.items():
            if pid in P:
                P[pid]["smart_tags"]["ticket"] = t
                P[pid]["ticket_note"] = note
        for pid, note in ACCESS.items():
            if pid in P:
                prev = P[pid].get("access_note", "")
                P[pid]["access_note"] = (prev + " | " if prev else "") + note
        for pid, (b, note) in PRICE.items():
            if pid in P:
                P[pid]["smart_tags"]["price_band"] = b
                P[pid]["price_note"] = note
        before = len(data["pois"])
        data["pois"] = [p for p in data["pois"] if p["name"] not in DROP_NAMES]
        data["count"] = len(data["pois"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"dropped {before - len(data['pois'])}")
    print(f"parking notes: {n_park} (dry-run counts new only with --apply off)")
    from BE.app.services.snapshot import load_snapshot  # noqa
    if args.apply:
        load_snapshot(args.snapshot)
        print("snapshot valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
