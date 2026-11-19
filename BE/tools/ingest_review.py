"""Turn a `review_v21_*.json` export (reports/p0/review_v21.html) into the
source files `migrate_v2.py` reads. Never edits pois.json.

    python BE/tools/ingest_review.py BE/data/sources/review_v21_20261119.json
    python BE/ml/data/migrate_v2.py

Writes (same date as the export):
- BE/data/sources/decisions_review_<date>.json   names, status, duplicates, old-town ticket
- BE/data/sources/human_verify_v2_<date>.json    hours / price tier / VND + evidence URL
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "BE", "data", "sources")

_DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_VI_DAY = {"hai": "Mo", "ba": "Tu", "tư": "We", "năm": "Th", "sáu": "Fr", "bảy": "Sa"}


def norm_hours(text):
    """Free-text hours typed in the review page -> (["HH:MM-HH:MM", ...], closed_days).
    '24h' / '24/7' / 'luôn mở' -> 00:00-23:59; '7h30 – 21h00' -> 07:30-21:00;
    'A và B' -> two spans; '17:00-23:00/1:00' keeps the first close time;
    'từ thứ Hai đến thứ Bảy' -> closed Su. ([], []) when nothing parses."""
    if not text:
        return [], []
    s = str(text).lower()
    if re.search(r"24\s*/\s*7|24h\b|24 giờ|luôn mở", s) and not re.search(r"\d{1,2}[:h]\d{2}\s*[-–]", s):
        return ["00:00-23:59"], []
    s = re.sub(r"(\d{1,2})h(\d{2})?", lambda m: f"{m.group(1)}:{m.group(2) or '00'}", s)
    s = s.replace("–", "-").replace("—", "-")
    spans = []
    for o, c in re.findall(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", s):
        oh, om = o.split(":")
        ch, cm = c.split(":")
        ch = "23" if ch == "24" else ch
        cm = "59" if c.startswith("24") else cm
        spans.append(f"{int(oh):02d}:{om}-{int(ch):02d}:{cm}")
    closed = []
    m = re.search(r"thứ\s+(hai|ba|tư|năm|sáu|bảy)\s+đến\s+(thứ\s+(hai|ba|tư|năm|sáu|bảy)|chủ nhật)", s)
    if m:
        a = _DAYS.index(_VI_DAY[m.group(1)])
        b = 6 if m.group(2) == "chủ nhật" else _DAYS.index(_VI_DAY[m.group(3)])
        closed = [d for i, d in enumerate(_DAYS) if not a <= i <= b]
    return spans, closed


def convert(export: dict) -> tuple[dict, dict]:
    if export.get("schema") != "review_v21":
        raise ValueError("not a review_v21 export")
    when = export.get("exported_at")
    items: dict[str, dict] = {}

    def put(pid, **kv):
        items.setdefault(pid, {}).update({k: v for k, v in kv.items() if v is not None})

    for n in export.get("names", []):
        if n.get("name") and n["name"] != n.get("name_was"):
            put(n["poi_id"], name=n["name"])
    for s in export.get("status", []):
        put(s["poi_id"], status=s["status"], status_reason=s.get("reason"))
    for d in export.get("duplicates", []):
        if d["decision"] == "keep_a":
            put(d["b"], status="excluded", status_reason=f"trùng với {d['a']}")
        elif d["decision"] == "keep_b":
            put(d["a"], status="excluded", status_reason=f"trùng với {d['b']}")
    ot = export.get("old_town") or {}
    for pid in ot.get("include", []):
        put(pid, requires_ticket_of=ot.get("parent"))
    for pid in ot.get("exclude", []):
        items.setdefault(pid, {})["requires_ticket_of"] = None
    out_verify, unparsed = [], []
    for v in export.get("verify", []):
        if re.search(r"xóa địa điểm", v.get("note") or "", re.I):
            put(v["poi_id"], status="excluded", status_reason="người dùng yêu cầu xóa")
            continue
        it = {**v, "checked_at": when, "verified_by": "human" if v.get("evidence_url") else "user"}
        if v.get("hours"):
            spans, closed = norm_hours(v["hours"])
            if spans:
                it["hours_raw"], it["hours"] = v["hours"], ", ".join(spans)
                if closed:
                    it["closed_days"] = closed
            else:
                unparsed.append(v["poi_id"])
        out_verify.append(it)
    decisions = {"note": f"Từ {export.get('exported_at')} (review_v21.html). Q: {json.dumps(export.get('questions'), ensure_ascii=False)}",
                 "items": items}
    verify = {"note": "review_v21.html export", "unparsed_hours": unparsed, "items": out_verify}
    return decisions, verify


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    with open(argv[0], encoding="utf-8") as f:
        export = json.load(f)
    decisions, verify = convert(export)
    tag = (export.get("exported_at") or "").replace("-", "")
    for name, obj in ((f"decisions_review_{tag}.json", decisions), (f"human_verify_v2_{tag}.json", verify)):
        path = os.path.join(SRC, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("wrote", path)
    print(f"decisions: {len(decisions['items'])} POI · verify: {len(verify['items'])} POI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
