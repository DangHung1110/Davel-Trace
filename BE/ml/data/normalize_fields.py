"""Deterministic field normalisation before verify (Phase 4, group A).

Every rule is a pure function of fields already in the snapshot: no source
is called and no value is guessed, so the output is exact and re-runnable
(idempotent). Run it after the enrichment tools (enrich_tags, ingest_money).

  fee            <- ticket_vnd (web-verified adult ticket). The planner budget,
                    savings profile and gate read `fee` only.
  price_level    <- smart_tags.price_band (cheap 1 / medium 2 / expensive 3);
                    no band -> null. The crawl wrote 2 as a placeholder.
  hours_source   "inferred" when the web fill was a guess ("suy luận ..."); on
                    a business (restaurant/cafe/bar/spa) the guess is dropped,
                    since an open-access reason cannot describe a shop.
  opening_hours  same-day sessions from a web/OSM fill joined into one element:
                    the planner reads separate elements as weekday variants.
  visit_min      category_rule durations recomputed from `duration_category`
                    (reviewed `cat`, not the raw Google type). Human durations
                    are never touched.

`--safe-hours` prints the measured hours the planner assumes for a POI with
none (BE.common.SAFE_HOURS); missing hours stay missing in the data.

Usage (repo root):
  python BE/ml/data/normalize_fields.py --snapshot BE/data/snapshots/danang-v1 --check
  python BE/ml/data/normalize_fields.py --snapshot BE/data/snapshots/danang-v1 --apply
  python BE/ml/data/normalize_fields.py --snapshot BE/data/snapshots/danang-v1 --safe-hours
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.common import (  # noqa: E402
    DAY_MIN, SAFE_HOURS_SHARE, day_spans, hhmm, hours_group, open_windows)
from BE.ml.patm.estimate_duration import (  # noqa: E402
    DUR_SOURCE, duration_category, estimate)

PRICE_LEVEL = {"cheap": 1, "medium": 2, "expensive": 3}
BUSINESS_CATS = {"restaurant", "cafe", "bar", "spa"}
INFERRED_PREFIX = "suy luận"
# Fills that write one element per session of the same day; Google crawl
# rows (no hours_source) keep one element per weekday variant.
SESSION_SOURCES = {"web", "osm", "osm-converted"}


def fee_rule(p: dict) -> str | None:
    ticket = p.get("ticket_vnd")
    if isinstance(ticket, int) and ticket > 0 and p.get("fee") != ticket:
        p["fee"] = ticket
        return "fee"
    return None


def price_level_rule(p: dict) -> str | None:
    level = PRICE_LEVEL.get((p.get("smart_tags") or {}).get("price_band"))
    if p.get("price_level") != level:
        p["price_level"] = level
        return "price_level" if level is not None else "price_level_null"
    return None


def inferred_hours_rule(p: dict) -> str | None:
    note = str((p.get("web_evidence") or {}).get("hours_web") or "")
    if p.get("hours_source") != "web" or not note.lower().startswith(INFERRED_PREFIX):
        return None
    if p.get("cat") in BUSINESS_CATS:
        p["opening_hours"] = []
        p["hours_source"] = "inferred_dropped"
        return "hours_inferred_dropped"
    p["hours_source"] = "inferred"
    return "hours_inferred"


def session_hours_rule(p: dict) -> str | None:
    hours = p.get("opening_hours") or []
    if p.get("hours_source") not in SESSION_SOURCES or len(hours) < 2:
        return None
    spans = sorted(s for h in hours for s in day_spans(h))
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        return None  # overlapping elements are weekday variants, not sessions
    p["opening_hours"] = [", ".join(hours)]
    return "hours_sessions_joined"


def duration_rule(p: dict) -> str | None:
    if p.get("dur_source") != DUR_SOURCE:
        return None
    r = estimate(duration_category(p), p.get("rating"), p.get("tags", []))
    new = {"p25": r["p25"], "p50": r["p50"], "p75": r["p75"]}
    if p.get("visit_min") == new:
        return None
    p["visit_min"] = new
    return "visit_min"


RULES = (fee_rule, price_level_rule, inferred_hours_rule, session_hours_rule,
         duration_rule)

# Hours that are themselves assumptions never feed the safe-hours measure.
ASSUMED_HOURS_SOURCES = {"inferred", "inferred_dropped", "rule_open_access",
                         "rule_temple_default"}


def safe_hours(pois: list[dict], share: float = SAFE_HOURS_SHARE, step: int = 15,
               min_len: int = 60) -> dict[str, list[str]]:
    """Measure `BE.common.SAFE_HOURS`: per hours group, the runs of `step`
    minutes in which >= `share` of the POIs with sourced hours are open
    (runs shorter than `min_len` dropped). [] = no such time."""
    groups: dict[str, list] = {}
    for p in pois:
        group = hours_group(p.get("cat") or "")
        wins = open_windows(p.get("opening_hours"))
        if group and wins and p.get("hours_source") not in ASSUMED_HOURS_SOURCES:
            groups.setdefault(group, []).append(wins)
    out = {}
    for group, rows in sorted(groups.items()):
        runs, run = [], None
        for t in range(0, DAY_MIN, step):
            open_share = sum(any(lo <= t and t + step <= hi for lo, hi in w)
                             for w in rows) / len(rows)
            if open_share >= share:
                run = (run[0], t + step) if run else (t, t + step)
            else:
                if run:
                    runs.append(run)
                run = None
        if run:
            runs.append(run)
        out[group] = [f"{hhmm(a)}-{hhmm(b % DAY_MIN)}" for a, b in runs
                      if b - a >= min_len]
    return out


def normalize(pois: list[dict]) -> dict[str, Counter]:
    """Apply every rule in place; {"all": changes, "verified": changes}."""
    report = {"all": Counter(), "verified": Counter()}
    for p in pois:
        for rule in RULES:
            change = rule(p)
            if change:
                report["all"][change] += 1
                if p.get("verified"):
                    report["verified"][change] += 1
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report, write nothing")
    mode.add_argument("--apply", action="store_true", help="rewrite pois.json")
    mode.add_argument("--safe-hours", action="store_true",
                      help="print the measured BE.common.SAFE_HOURS table")
    args = ap.parse_args(argv)
    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if args.safe_hours:
        print(json.dumps(safe_hours(data["pois"]), ensure_ascii=False, indent=4))
        return 0
    report = normalize(data["pois"])
    for scope, changes in report.items():
        print(f"{scope}: " + (", ".join(f"{k}={v}" for k, v in sorted(changes.items()))
                              or "no change"))
    if args.apply:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
