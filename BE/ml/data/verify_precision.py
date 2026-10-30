"""Score the blind precision sample (Phase 4 gate, docs/verify-proposal.md 3.3).

Reads the files exported by FE/verify_sample.html (one per reviewer) and
reports, for the auto-verify batch the sample was drawn from:

  - precision per reviewer and STRICT (a POI counts as correct only when
    every reviewer who graded it said "dung"), with a Wilson 95% interval;
  - Cohen's kappa and raw agreement between two reviewers on shared POIs;
  - which fields were wrong (flags) and the precision per category.

Gate: strict precision >= 95% AND the interval's lower bound >= 90%. A miss
means the batch is not trusted as is: re-check its single/conflict rows
(osm_crosscheck.json) rather than un-verifying all of it.

  python BE/ml/data/verify_precision.py --snapshot BE/data/snapshots/danang-v1 \\
      verify_verdicts_sample_20261030_A.jsonl verify_verdicts_sample_20261030_B.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter, defaultdict

GATE_PRECISION = 0.95
GATE_LOWER = 0.90


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def cohen_kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Kappa for two raters' binary labels; None when undefined."""
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n
    pb = sum(b for _, b in pairs) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


def load(paths: list[str]) -> dict[str, dict[str, dict]]:
    """{reviewer: {poi_id: line}} from sample-page files (last line wins)."""
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for path in paths:
        with open(path, encoding="utf-8-sig") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                line = json.loads(raw)
                if line.get("page") != "sample" or line.get("verdict") not in ("dung", "sai"):
                    continue
                out[str(line.get("reviewer") or os.path.basename(path)).strip()][line["poi_id"]] = line
    return out


def score(by_reviewer: dict[str, dict[str, dict]], cats: dict[str, str] | None = None) -> dict:
    cats = cats or {}
    reviewers = sorted(by_reviewer)
    report: dict = {"reviewers": {}, "gate": {"precision": GATE_PRECISION, "lower": GATE_LOWER}}
    for name in reviewers:
        lines = by_reviewer[name]
        k = sum(1 for l in lines.values() if l["verdict"] == "dung")
        lo, hi = wilson(k, len(lines))
        report["reviewers"][name] = {"graded": len(lines), "correct": k,
                                     "precision": round(k / len(lines), 4) if lines else None,
                                     "ci95": [round(lo, 4), round(hi, 4)]}
    graded = sorted({pid for name in reviewers for pid in by_reviewer[name]})
    correct = [pid for pid in graded
               if all(by_reviewer[n][pid]["verdict"] == "dung"
                      for n in reviewers if pid in by_reviewer[n])]
    lo, hi = wilson(len(correct), len(graded))
    precision = len(correct) / len(graded) if graded else None
    report["strict"] = {"graded": len(graded), "correct": len(correct),
                        "precision": round(precision, 4) if precision is not None else None,
                        "ci95": [round(lo, 4), round(hi, 4)],
                        "pass": bool(graded) and precision >= GATE_PRECISION and lo >= GATE_LOWER}
    if len(reviewers) >= 2:
        a, b = reviewers[:2]
        shared = sorted(set(by_reviewer[a]) & set(by_reviewer[b]))
        pairs = [(by_reviewer[a][p]["verdict"] == "dung", by_reviewer[b][p]["verdict"] == "dung")
                 for p in shared]
        kappa = cohen_kappa(pairs)
        report["agreement"] = {
            "reviewers": [a, b], "shared": len(shared),
            "raw": round(sum(x == y for x, y in pairs) / len(pairs), 4) if pairs else None,
            "kappa": round(kappa, 4) if kappa is not None else None,
            "disagree": [p for p, (x, y) in zip(shared, pairs) if x != y]}
    flags = Counter(f for name in reviewers for l in by_reviewer[name].values()
                    for f in l.get("flags") or [])
    report["flags"] = dict(flags.most_common())
    per_cat = defaultdict(lambda: [0, 0])
    for pid in graded:
        per_cat[cats.get(pid, "?")][1] += 1
        per_cat[cats.get(pid, "?")][0] += pid in correct
    report["by_cat"] = {c: {"correct": k, "graded": n} for c, (k, n) in sorted(per_cat.items())}
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+", help="verify_verdicts_sample_*.jsonl, one per reviewer")
    ap.add_argument("--snapshot", help="adds per-category precision (reads pois.json)")
    ap.add_argument("--out", help="also write the report as JSON")
    args = ap.parse_args(argv)
    cats = {}
    if args.snapshot:
        with open(os.path.join(args.snapshot, "pois.json"), encoding="utf-8") as f:
            cats = {p["poi_id"]: p.get("cat") or "" for p in json.load(f)["pois"]}
    report = score(load(args.files), cats)
    for name, r in report["reviewers"].items():
        print(f"{name}: {r['correct']}/{r['graded']} = {r['precision']} CI95 {r['ci95']}")
    s = report["strict"]
    print(f"STRICT: {s['correct']}/{s['graded']} = {s['precision']} CI95 {s['ci95']} -> "
          f"{'PASS' if s['pass'] else 'FAIL'} (gate >= {GATE_PRECISION}, lower >= {GATE_LOWER})")
    if "agreement" in report:
        g = report["agreement"]
        print(f"agreement {g['reviewers']}: shared {g['shared']}, raw {g['raw']}, "
              f"kappa {g['kappa']}, disagree {len(g['disagree'])}")
    print(f"wrong fields: {report['flags']}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
            f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
