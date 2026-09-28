"""Duration estimator nac-1 (T003c): category defaults x modifiers -> p25/p50/p75.

Research R8: no public source gives visit duration for Da Nang POIs, so
nac-1 uses rule defaults. Nac-2 (LLM batch, pending T003b snapshot) will
refine; nac-3 (review mining) is P3 backlog T060.

Rules (R8 exact):
  - base p50 from CATEGORY_DEFAULTS (minutes)
  - rating >= 4.5 -> x1.2
  - tag contains "rong"/"lon" (rong/lon = wide/large, diacritics-insensitive) -> x1.3
  - tag contains "check-in"/"nhe" (light/quick stop) -> x0.7
  - modifiers multiply sequentially, p50 rounded to int
  - p25 = round(p50 * 0.7), p75 = round(p50 * 1.4)
  - output: visit_min{p25,p50,p75}, dur_source="category_rule", dur_confidence="low"

Semantics (data-model.md): optimizer schedules with p50; gate checks p75
buffer (FR-019); UI shows "~p25-p75 phut (uoc tinh)", never as fact.

Usage:
  python BE/ml/patm/estimate_duration.py data/snapshots/danang-v1/pois.json
  python BE/ml/patm/estimate_duration.py --check data/snapshots/danang-v1/pois.json
"""

from __future__ import annotations

import json
import sys
import unicodedata

CATEGORY_DEFAULTS: dict[str, int] = {
    "landmark": 45,
    "transport": 20,
    "market": 75,
    "nature": 150,
    "restaurant": 60,
    "museum": 90,
    "beach": 120,
}

DEFAULT_P50 = 60
DUR_SOURCE = "category_rule"
DUR_CONFIDENCE = "low"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def modifiers_for(rating: float | None, tags: list[str]) -> list[str]:
    applied: list[str] = []
    if rating is not None and rating >= 4.5:
        applied.append("rating>=4.5 x1.2")
    tnorm = [_norm(t) for t in (tags or [])]
    words = {w for t in tnorm for w in t.replace("-", " ").split()}
    if "rong" in words or "lon" in words:
        applied.append("tag rong/lon x1.3")
    if any("check-in" in t or "checkin" in t for t in tnorm) or "nhe" in words:
        applied.append("tag check-in/nhe x0.7")
    return applied


def estimate(category: str, rating: float | None = None,
             tags: list[str] | None = None) -> dict:
    """Return {p25, p50, p75, dur_source, dur_confidence, applied}."""
    tags = tags or []
    p50 = float(CATEGORY_DEFAULTS.get(category, DEFAULT_P50))
    applied = modifiers_for(rating, tags)
    for rule in applied:
        factor = float(rule.split("x")[1])
        p50 *= factor
    p50 = int(round(p50))
    return {
        "p25": int(round(p50 * 0.7)),
        "p50": p50,
        "p75": int(round(p50 * 1.4)),
        "dur_source": DUR_SOURCE,
        "dur_confidence": DUR_CONFIDENCE,
        "applied": applied,
    }


def enrich_poi(poi: dict) -> dict:
    """Fill visit_min/dur_* on a POI dict in place; return it."""
    r = estimate(poi.get("type", ""), poi.get("rating"), poi.get("tags", []))
    poi["visit_min"] = {"p25": r["p25"], "p50": r["p50"], "p75": r["p75"]}
    poi["dur_source"] = r["dur_source"]
    poi["dur_confidence"] = r["dur_confidence"]
    return poi


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    paths = [a for a in argv[1:] if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    rc = 0
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pois = data if isinstance(data, list) else data.get("pois", [])
        bad = 0
        for poi in pois:
            r = estimate(poi.get("type", ""), poi.get("rating"), poi.get("tags", []))
            if check_only:
                vm = poi.get("visit_min", {})
                if (vm.get("p25"), vm.get("p50"), vm.get("p75")) != (r["p25"], r["p50"], r["p75"]) \
                        or poi.get("dur_source") != DUR_SOURCE:
                    print(f'MISMATCH {poi.get("poi_id")}: file={vm} '
                          f'rule={r["p25"], r["p50"], r["p75"]} {r["applied"]}')
                    bad += 1
                else:
                    print(f'OK {poi.get("poi_id")}: p25={r["p25"]} p50={r["p50"]} '
                          f'p75={r["p75"]} {r["applied"] or "no-mod"}')
            else:
                enrich_poi(poi)
                print(f'{poi.get("poi_id")}: p25={r["p25"]} p50={r["p50"]} p75={r["p75"]}')
        if check_only:
            print(f"{path}: {len(pois) - bad}/{len(pois)} match nac-1 rules")
            rc = rc or (1 if bad else 0)
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data if isinstance(data, list) else data, f,
                          ensure_ascii=False, indent=2)
                f.write("\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
