"""Ingest human review verdicts into pois.json (Phase 4, docs/verify-proposal.md 6.6).

Reads the JSONL files exported by FE/verify_review.html (BE/tools/
build_verify_page.py documents the line format) and applies them, dry-run by
default:

  dung   verified=true, verified_by=human-review-v1 (+ edits)
  loai   verified=false; spotcheck_v2 never auto-passes the POI again
  edits  opening_hours (hours_source=human), cat, visit_p50 (visit_min
         p25/p75 = 0.7x/1.4x, dur_source=human), ticket_vnd, price_band;
         then normalize_fields runs (fee, price_level follow)

A line is rejected, never half-applied, when:
  - the schema is wrong (unknown poi_id or verdict, empty reviewer, bad edit);
  - it comes from the sample page (scored by verify_precision.py, not here);
  - its row_hash differs from the POI today: the data changed after the page
    was built, so the verdict may be about other values (rebuild the page).
Reviewers who disagree on a POI's verdict leave it untouched (reported);
agreeing reviewers who typed different values for one field drop that edit.
A line already applied (same reviewer and ts in `review`) is skipped, so a
re-run is a no-op. Every applied line is appended to review_log.jsonl.

  python BE/ml/data/ingest_verdicts.py --snapshot BE/data/snapshots/danang-v1 \\
      verify_verdicts_review_20261030_Lan.jsonl [more.jsonl] [--apply]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from collections import Counter, defaultdict

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.common import day_spans  # noqa: E402
from BE.ml.data.normalize_fields import normalize  # noqa: E402
from BE.tools.build_verify_page import KNOWN_CATS, PRICE_BANDS, row_hash  # noqa: E402

VERIFIED_BY = "human-review-v1"
VERDICTS = {"dung", "loai"}
EDIT_FIELDS = {"opening_hours", "cat", "visit_p50", "ticket_vnd", "price_band"}
HOURS_RE = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}(, \d{2}:\d{2}-\d{2}:\d{2})*$")


def edit_errors(edits) -> list[str]:
    if not isinstance(edits, dict):
        return ["edits is not an object"]
    errors = [f"unknown edit {k}" for k in edits if k not in EDIT_FIELDS]
    hours = edits.get("opening_hours")
    if hours is not None and not (
            isinstance(hours, list) and hours and
            all(isinstance(h, str) and HOURS_RE.match(h) and day_spans(h) for h in hours)):
        errors.append(f"bad opening_hours {hours!r}")
    if "cat" in edits and edits["cat"] not in KNOWN_CATS:
        errors.append(f"bad cat {edits['cat']!r}")
    for field, lo, hi in (("visit_p50", 5, 600), ("ticket_vnd", 0, 5_000_000)):
        value = edits.get(field)
        if field in edits and not (isinstance(value, int) and not isinstance(value, bool)
                                   and lo <= value <= hi):
            errors.append(f"bad {field} {value!r}")
    if "price_band" in edits and edits["price_band"] not in PRICE_BANDS:
        errors.append(f"bad price_band {edits['price_band']!r}")
    return errors


def already_applied(poi: dict, line: dict) -> bool:
    review = poi.get("review") or {}
    return any(r.get("reviewer") == line.get("reviewer") and r.get("ts") == line.get("ts")
               for r in review.get("by", []))


def check_line(line: dict, pois: dict) -> str | None:
    """Rejection reason, or None when the line can be used."""
    if line.get("page") == "sample":
        return "sample page (score with verify_precision.py)"
    poi = pois.get(line.get("poi_id"))
    if poi is None:
        return "unknown poi_id"
    if line.get("verdict") not in VERDICTS:
        return f"bad verdict {line.get('verdict')!r}"
    if not str(line.get("reviewer") or "").strip():
        return "empty reviewer"
    if not str(line.get("ts") or ""):
        return "missing ts"
    errors = edit_errors(line.get("edits", {}))
    if errors:
        return "; ".join(errors)
    if already_applied(poi, line):
        return "already applied"
    if line.get("row_hash") and line["row_hash"] != row_hash(poi):
        return "stale: POI changed since the page was built"
    return None


def read_lines(paths: list[str]) -> list[tuple[str, int, dict | None, str]]:
    out = []
    for path in paths:
        with open(path, encoding="utf-8-sig") as f:
            for n, raw in enumerate(f, 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    out.append((path, n, json.loads(raw), ""))
                except json.JSONDecodeError as exc:
                    out.append((path, n, None, f"invalid JSON: {exc}"))
    return out


def plan_ingest(lines, pois: dict) -> dict:
    """Decide what to apply. Pure: reads `pois`, never writes it."""
    rejected, accepted = [], []
    for path, n, line, err in lines:
        reason = err or check_line(line, pois)
        if reason:
            rejected.append({"file": os.path.basename(path), "line": n,
                             "poi_id": (line or {}).get("poi_id"), "reason": reason})
        else:
            accepted.append(dict(line, _file=os.path.basename(path)))
    # last line per (poi, reviewer) wins, as the export contract says
    latest: dict[tuple, dict] = {}
    for line in accepted:
        latest[(line["poi_id"], line["reviewer"].strip())] = line
    by_poi = defaultdict(list)
    for (pid, _), line in latest.items():
        by_poi[pid].append(line)
    apply, conflicts, dropped_edits = {}, [], []
    for pid, group in by_poi.items():
        verdicts = {g["verdict"] for g in group}
        if len(verdicts) > 1:
            conflicts.append({"poi_id": pid, "name": pois[pid].get("name"),
                              "verdicts": {g["reviewer"]: g["verdict"] for g in group}})
            continue
        edits: dict = {}
        for field in EDIT_FIELDS:
            values = {json.dumps(g["edits"][field], ensure_ascii=False)
                      for g in group if field in g.get("edits", {})}
            if len(values) == 1:
                edits[field] = json.loads(values.pop())
            elif values:
                dropped_edits.append({"poi_id": pid, "field": field, "values": sorted(values)})
        apply[pid] = {"verdict": verdicts.pop(), "edits": edits, "lines": group}
    return {"apply": apply, "rejected": rejected, "conflicts": conflicts,
            "dropped_edits": dropped_edits}


def apply_one(poi: dict, decision: dict, today: str) -> None:
    edits = decision["edits"]
    if "opening_hours" in edits:
        poi["opening_hours"] = edits["opening_hours"]
        poi["hours_source"] = "human"
    if "cat" in edits:
        poi["cat"] = edits["cat"]
    if "visit_p50" in edits:
        p50 = edits["visit_p50"]
        poi["visit_min"] = {"p25": round(p50 * 0.7), "p50": p50, "p75": round(p50 * 1.4)}
        poi["dur_source"], poi["dur_confidence"] = "human", "medium"
    tags = poi.setdefault("smart_tags", {})
    if "ticket_vnd" in edits:
        poi["ticket_vnd"] = edits["ticket_vnd"]
        tags["ticket"] = edits["ticket_vnd"] > 0
        if edits["ticket_vnd"] == 0:
            poi["fee"] = 0
    if "price_band" in edits:
        tags["price_band"] = edits["price_band"]
        tags["band_verified"] = True
    if decision["verdict"] == "dung":
        poi["verified"], poi["verified_by"], poi["verified_at"] = True, VERIFIED_BY, today
    else:
        poi["verified"] = False
        poi.pop("verified_by", None)
        poi.pop("verified_at", None)
    review = poi.setdefault("review", {"by": []})
    review["verdict"] = decision["verdict"]
    review["by"] = review.get("by", []) + [
        dict({"reviewer": g["reviewer"].strip(), "ts": g["ts"], "note": g.get("note") or "",
              "file": g["_file"]}, **({"draft_by": g["draft_by"]} if g.get("draft_by") else {}))
        for g in decision["lines"]]
    if edits:
        review["edits"] = sorted(set(review.get("edits", [])) | set(edits))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("files", nargs="+", help="verify_verdicts_review_*.jsonl")
    ap.add_argument("--apply", action="store_true", help="write pois.json (default: dry run)")
    args = ap.parse_args(argv)
    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    pois = {p["poi_id"]: p for p in data["pois"]}
    plan = plan_ingest(read_lines(args.files), pois)

    verdicts = Counter(d["verdict"] for d in plan["apply"].values())
    edits = Counter(k for d in plan["apply"].values() for k in d["edits"])
    print(f"apply: {len(plan['apply'])} POI ({dict(verdicts)}), edits {dict(edits)}")
    print(f"rejected lines: {len(plan['rejected'])} "
          f"{dict(Counter(r['reason'].split(':')[0] for r in plan['rejected']))}")
    for r in plan["rejected"][:20]:
        print(f"  - {r['file']}:{r['line']} {r['poi_id']}: {r['reason']}")
    print(f"reviewer conflicts (not applied): {len(plan['conflicts'])}")
    for c in plan["conflicts"]:
        print(f"  - {c['name']} {c['verdicts']}")
    print(f"edits dropped (reviewers typed different values): {len(plan['dropped_edits'])}")
    for d in plan["dropped_edits"]:
        print(f"  - {d['poi_id']} {d['field']}: {d['values']}")
    if not args.apply:
        print("dry run: nothing written (re-run with --apply)")
        return 0

    today = datetime.date.today().isoformat()
    for pid, decision in plan["apply"].items():
        apply_one(pois[pid], decision, today)
    normalized = normalize(data["pois"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log_path = os.path.join(args.snapshot, "review_log.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        for pid, decision in sorted(plan["apply"].items()):
            for g in decision["lines"]:
                entry = {k: v for k, v in g.items() if not k.startswith("_")}
                f.write(json.dumps(dict(entry, file=g["_file"], applied_at=today),
                                   ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote {path}; normalize: {dict(normalized['all']) or 'no change'}; "
          f"log -> {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
