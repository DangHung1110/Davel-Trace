"""Pair dataset builder (T028-BUILDER, lane A). Protocol T028, stdlib only.

Target: 1,500-2,000 pairs (min viable 500-1,000) from the FULL snapshot
(T003b, pending). Sources: 1000 rule / 600 LLM-judge / 200 human.
This module implements the builder + protocol scaffolding; it does NOT
close T028 (needs full snapshot + real Qwen judge batch first).

Protocol pieces:
- RULE LABELS (this file, runnable now): deterministic order preference
  from POI attributes (intensity curve, meal-after-activity, indoor buffer
  for weather-sensitive pairs). Hook: when T027 `rule_score.py` lands,
  replace `_rule_margin` internals with it (same signature).
- BALANCE 30/40/30: label mix target = 30% prefer-first / 40% tie /
  30% prefer-second. `--check` reports the mix; builder subsamples ties
  to hold it.
- SWAP-CHECK: every pair is stored in both orders (a,b) and (b,a);
  `swap_check` asserts antisymmetry (label flips, tie stays tie).
  `--drop-contradictions` removes the LLM pairs answered both ways.
- NO POI LEAKAGE: `leave_poi_out_split` hides 20% of POI ids from train;
  any pair touching a held-out POI goes to eval (T031 generalization proof).

Pair record:
  {"pair_id", "first_id", "second_id", "label" (+1 first better / 0 tie /
   -1 second better), "margin", "source" (rule|llm|human), "rules"[fired],
   "swapped_from" (pair_id of the mirror or null)}

Usage:
  python BE/ml/patm/make_pairs.py --snapshot data/snapshots/danang-v1 --n 42 --seed 7
  python BE/ml/patm/make_pairs.py --snapshot ... --check pairs.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.common import load_pois  # noqa: E402
from BE.ml.patm.rule_score import (  # noqa: E402
    TIE_MARGIN,  # re-exported for callers that used make_pairs.TIE_MARGIN
    explain_transition as _explain,
    score_transition as _rule_score,
)

LABEL_NAMES = {1: "prefer-first", 0: "tie", -1: "prefer-second"}


def _rule_margin(a: dict, b: dict) -> tuple[float, list[str]]:
    """Signed margin >0 means a->b beats b->a. Delegates to T027 scorer."""
    return _rule_score(a, b), _explain(a, b)


def label_ordered(a: dict, b: dict) -> dict:
    margin, fired = _rule_margin(a, b)
    label = 1 if margin > TIE_MARGIN else (-1 if margin < -TIE_MARGIN else 0)
    return {"label": label, "margin": round(margin, 3), "rules": fired}


def build_rule_pairs(pois: list[dict], n: int, seed: int = 7) -> list[dict]:
    """All unordered POI pairs x both orders, subsampled to n keeping 30/40/30."""
    rng = random.Random(seed)
    by_label: dict[int, list[dict]] = {1: [], 0: [], -1: []}
    for a, b in itertools.combinations(sorted(pois, key=lambda p: p["poi_id"]), 2):
        lab = label_ordered(a, b)
        fwd = {"pair_id": f"rule-{a['poi_id']}-vs-{b['poi_id']}",
               "first_id": a["poi_id"], "second_id": b["poi_id"],
               "label": lab["label"], "margin": lab["margin"],
               "source": "rule", "rules": lab["rules"], "swapped_from": None}
        back = {"pair_id": fwd["pair_id"] + "-swap",
                "first_id": b["poi_id"], "second_id": a["poi_id"],
                "label": -lab["label"], "margin": -lab["margin"],
                "source": "rule", "rules": lab["rules"], "swapped_from": fwd["pair_id"]}
        fwd["swapped_from"] = back["pair_id"]
        by_label[lab["label"]].append(fwd)
        by_label[-lab["label"]].append(back)
    # 30/40/30 quota over ordered pairs (mirror pairs share the quota pool)
    quota = {1: int(n * 0.3), 0: int(n * 0.4), -1: n - int(n * 0.3) - int(n * 0.4)}
    out: list[dict] = []
    for label, q in quota.items():
        pool = by_label[label]
        rng.shuffle(pool)
        out.extend(pool[:q])
    rng.shuffle(out)
    return out


def swap_check(pairs: list[dict]) -> dict:
    """Antisymmetry audit: mirror labels must flip (tie stays tie)."""
    by_id = {p["pair_id"]: p for p in pairs}
    checked, bad = 0, 0
    for p in pairs:
        mirror = by_id.get(p.get("swapped_from") or "")
        if mirror is None:
            continue
        checked += 1
        if mirror["label"] != -p["label"]:
            bad += 1
    return {"checked": checked, "inconsistent": bad,
            "rate": (checked - bad) / checked if checked else 1.0}


def balance_report(pairs: list[dict]) -> dict:
    total = len(pairs) or 1
    counts = {1: 0, 0: 0, -1: 0}
    for p in pairs:
        counts[p["label"]] += 1
    return {"n": len(pairs),
            "mix": {LABEL_NAMES[k]: round(v / total, 3) for k, v in counts.items()}}


def check_pairs(pairs: list[dict]) -> list[str]:
    """Format + balance + POI-leakage sanity (leakage checked via split)."""
    errors: list[str] = []
    required = ("pair_id", "first_id", "second_id", "label", "margin",
                "source", "rules", "swapped_from")
    seen: set[str] = set()
    for p in pairs:
        for k in required:
            if k not in p:
                errors.append(f"{p.get('pair_id', '?')}: missing '{k}'")
        if p.get("pair_id") in seen:
            errors.append(f"duplicate pair_id {p.get('pair_id')}")
        seen.add(p.get("pair_id"))
        if p.get("label") not in (1, 0, -1):
            errors.append(f"{p.get('pair_id')}: bad label {p.get('label')}")
        if p.get("first_id") == p.get("second_id"):
            errors.append(f"{p.get('pair_id')}: self-pair (POI leakage)")
        if p.get("source") not in ("rule", "llm", "human"):
            errors.append(f"{p.get('pair_id')}: bad source {p.get('source')}")
    return errors


def leave_poi_out_split(pairs: list[dict], frac: float = 0.2,
                        seed: int = 7) -> tuple[list[dict], list[dict], list[str]]:
    """Hide frac of POI ids; pairs touching them go to eval (T031)."""
    rng = random.Random(seed)
    ids = sorted({p["first_id"] for p in pairs} | {p["second_id"] for p in pairs})
    k = max(1, int(len(ids) * frac))
    held = set(rng.sample(ids, k))
    train = [p for p in pairs if p["first_id"] not in held and p["second_id"] not in held]
    eval_ = [p for p in pairs if p["first_id"] in held or p["second_id"] in held]
    train_ids = {p["first_id"] for p in train} | {p["second_id"] for p in train}
    leaked = sorted(train_ids & held)
    return train, eval_, leaked


def drop_self_contradictions(pairs: list[dict]) -> tuple[list[dict], int]:
    """Drop LLM pairs whose two orders disagree, return (kept, pairs dropped).

    The judge is asked both orders. An answer that follows the order of the
    question ("whichever is named first") says nothing about the places: 129 of
    466 pairs in v4. A pair asked in one order only cannot be checked and stays.
    """
    orders: dict[frozenset, list[dict]] = {}
    for pair in pairs:
        if pair.get("source") == "llm":
            orders.setdefault(frozenset((pair["first_id"], pair["second_id"])), []).append(pair)
    bad = set()
    for key, rows in orders.items():
        if len(rows) == 2:
            a, b = rows
            same_order = a["first_id"] == b["first_id"]
            if a["label"] != (b["label"] if same_order else -b["label"]):
                bad.add(key)
    kept = [p for p in pairs if p.get("source") != "llm"
            or frozenset((p["first_id"], p["second_id"])) not in bad]
    return kept, len(bad)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T028 pair builder")
    ap.add_argument("--snapshot", default="data/snapshots/danang-v1")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="")
    ap.add_argument("--check", default="")
    ap.add_argument("--drop-contradictions", nargs=2, metavar=("IN", "OUT"),
                    help="rewrite a pair file without self-contradicting LLM pairs")
    args = ap.parse_args(argv)

    if args.drop_contradictions:
        with open(args.drop_contradictions[0], encoding="utf-8") as f:
            kept, dropped = drop_self_contradictions(json.load(f))
        with open(args.drop_contradictions[1], "w", encoding="utf-8") as f:
            json.dump(kept, f, ensure_ascii=False)
        print(f"dropped {dropped} self-contradicting LLM pairs, {len(kept)} rows left")
        return 0
    if args.check:
        with open(args.check, encoding="utf-8") as f:
            pairs = json.load(f)
        errors = check_pairs(pairs)
        print(f"format: {len(pairs)} pairs, {len(errors)} errors")
        for e in errors[:10]:
            print("  ERR", e)
        print("balance:", balance_report(pairs))
        print("swap:", swap_check(pairs))
        train, eval_, leaked = leave_poi_out_split(pairs)
        print(f"leave-POI-out: train {len(train)} / eval {len(eval_)} / leaked {leaked}")
        return 1 if errors or leaked else 0

    pois = load_pois(args.snapshot)
    pairs = build_rule_pairs(pois, args.n, args.seed)
    print(f"built {len(pairs)} rule pairs from {len(pois)} POIs")
    print("balance:", balance_report(pairs))
    print("swap:", swap_check(pairs))
    train, eval_, leaked = leave_poi_out_split(pairs)
    print(f"leave-POI-out: train {len(train)} / eval {len(eval_)} / leaked {leaked}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(pairs, f, ensure_ascii=False, indent=2)
        print(f"wrote -> {args.out}")
    return 0 if not leaked else 1


if __name__ == "__main__":
    raise SystemExit(main())
