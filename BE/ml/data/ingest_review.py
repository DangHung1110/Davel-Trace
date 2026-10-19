"""Ingest review_answers.json into the snapshot (lane A).

Parses REVIEW_V2.md in the same order as render_review.py to map idx ->
item. D1 drop -> delete POI (+ persist id into prune REMOVE_IDS so future
crawls skip it). D1 keep / others ok -> nothing. Others fix -> listed
with notes for manual triage (free text can't auto-apply safely).

Usage: python BE/ml/data/ingest_review.py --snapshot ... [--apply]
Without --apply: dry run, prints what would happen.
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

ITEM_RE = re.compile(r"^- \[ \] (.*?) =>\s*$")
ID_RE = re.compile(r"\[([A-Za-z0-9:_/-]{4,})\]")


def load_items(snapshot: str):
    with open(os.path.join(snapshot, "REVIEW_V2.md"), encoding="utf-8") as f:
        lines = f.read().splitlines()
    items, sec, clu, idx = [], "", "", 0
    for ln in lines:
        if ln.startswith("## "):
            sec = ln[3:].strip()
        elif ln.startswith("### "):
            clu = ln[4:].strip()
        else:
            m = ITEM_RE.match(ln)
            if m:
                idx += 1
                items.append({"idx": idx, "sec": sec, "clu": clu,
                              "text": m.group(1)})
    return items


def resolve(text: str, pois: list[dict]) -> str | None:
    """Match 'NAME [PREFIX]' against exact name + id prefix (unique or None)."""
    m = re.match(r"^(.*?) \[([A-Za-z0-9:_/-]{4,})\]", text)
    if not m:
        return None
    name, pre = m.group(1), m.group(2)
    cands = [p["poi_id"] for p in pois if p["name"] == name]
    if len(cands) == 1:
        return cands[0]
    cands = [c for c in cands if c.startswith(pre)]
    if len(cands) == 1:
        return cands[0]
    if not cands:  # POI already removed earlier (D7 items) -> no-op
        return None
    return "AMBIGUOUS:" + "|".join(c[:8] for c in cands)


def resolve_all(text: str, pois: list[dict]) -> list[str]:
    """All ids with the exact name (for drop votes: same name = same verdict)."""
    m = re.match(r"^(.*?) \[", text)
    if not m:
        return []
    return [p["poi_id"] for p in pois if p["name"] == m.group(1)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    items = {s["idx"]: s for s in load_items(args.snapshot)}
    ans = json.load(open(os.path.join(args.snapshot, "review_answers.json"),
                         encoding="utf-8"))
    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    drops, fixes, missing = [], [], []
    for r in ans:
        s = items.get(r["idx"])
        if not s:
            missing.append(r["idx"])
            continue
        full = resolve(s["text"], data["pois"])
        if s["sec"].startswith("D1"):
            if r["v"] == "drop":
                m2 = re.match(r"^(.*?) \[", s["text"])
                # drop-all-same-name ONLY if every answered row for that
                # name voted drop (else we can't tell instances apart)
                sibs = [x for x in ans
                        if items.get(x["idx"], {}).get("text", "").startswith(m2.group(1) + " [")
                        and x["v"] == "drop"] if m2 else []
                allrows = [x for x in ans
                           if items.get(x["idx"], {}).get("text", "").startswith(m2.group(1) + " [")] if m2 else []
                if m2 and sibs and len(sibs) == len(allrows):
                    for i in resolve_all(s["text"], data["pois"]) or ["GONE"]:
                        drops.append((i, s["text"][:80], r.get("note", "")))
                else:
                    drops.append((full or "GONE", s["text"][:80], r.get("note", "")))
        elif r["v"] == "fix":
            fixes.append((full, s["sec"], s["text"][:100], r.get("note", "")))
    print(f"answered={len(ans)} drops={len(drops)} fixes={len(fixes)} "
          f"missing_idx={missing}")
    amb = [d for d in drops if (d[0] or "").startswith("AMBIGUOUS") or d[0] in (None, "GONE")]
    print(f"ambiguous/gone drops: {len(amb)}")
    for d in amb:
        print("  ??", d)
    if args.apply:
        ok_ids = {d[0] for d in drops if d[0] and not d[0].startswith("AMBIGUOUS") and d[0] != "GONE"}
        data["pois"] = [p for p in data["pois"] if p["poi_id"] not in ok_ids]
        data["count"] = len(data["pois"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"deleted {len(ok_ids)} POIs, kept {len(data['pois'])}")
    print("--- FIX items with notes ---")
    for full, sec, text, note in fixes:
        print(f"[{sec}] {text}\n    id={full}\n    note={note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
