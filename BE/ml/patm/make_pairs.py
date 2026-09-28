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
  Judge batch (Qwen) asks both orders too and drops inconsistent pairs.
- JUDGE BATCH (frame only, runs later): `--emit-judge-batch` writes a
  JSONL of prompts (name+category+rating+tags, both orders) for the
  overnight Qwen run (owner batch LLM: Bach); `--collect-judge` parses
  the returned JSONL into pairs. No judge data exists yet.
- HUMAN VERIFY: `sample_human` draws a stratified n (default 200)
  for the <=3-day human check after the batch.
- NO POI LEAKAGE: `leave_poi_out_split` hides 20% of POI ids from train;
  any pair touching a held-out POI goes to eval (T031 generalization proof).

Pair record:
  {"pair_id", "first_id", "second_id", "label" (+1 first better / 0 tie /
   -1 second better), "margin", "source" (rule|llm|human), "rules"[fired],
   "swapped_from" (pair_id of the mirror or null)}

Usage:
  python BE/ml/patm/make_pairs.py --snapshot data/snapshots/danang-v1 --n 42 --seed 7
  python BE/ml/patm/make_pairs.py --snapshot ... --check pairs.json
  python BE/ml/patm/make_pairs.py --snapshot ... --emit-judge-batch judge_q.jsonl
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

try:
    from BE.ml.patm.rule_score import (  # T027: canonical scorer
        TIE_MARGIN as _RULE_TIE,
        explain_transition as _explain,
        score_transition as _rule_score,
    )
    _HAS_RULE_SCORE = True
except ImportError:  # standalone copy (tests/CI without repo root)
    _HAS_RULE_SCORE = False

LABEL_NAMES = {1: "prefer-first", 0: "tie", -1: "prefer-second"}
TIE_MARGIN = _RULE_TIE if _HAS_RULE_SCORE else 0.15


def load_pois(snapshot_dir: str) -> list[dict]:
    with open(os.path.join(snapshot_dir, "pois.json"), encoding="utf-8") as f:
        return json.load(f)["pois"]


def _legacy_margin(a: dict, b: dict) -> tuple[float, list[str]]:
    """Pre-T027 inline rules. Kept as fallback + backward-compat oracle."""
    margin, fired = 0.0, []
    ia, ib = a.get("intensity", 2), b.get("intensity", 2)
    if ia > ib:  # van dong truoc, thu gian sau (spec US3: hiking -> beach)
        margin += 0.5
        fired.append("intensity-desc")
    elif ib > ia:
        margin -= 0.5
        fired.append("intensity-desc")
    if a.get("type") != "restaurant" and b.get("type") == "restaurant":
        margin += 0.3  # an sau hoat dong
        fired.append("meal-after-activity")
    elif b.get("type") != "restaurant" and a.get("type") == "restaurant":
        margin -= 0.3
        fired.append("meal-after-activity")
    if a.get("weather_sensitive") and not b.get("weather_sensitive"):
        margin -= 0.2  # uu tien trong-nha truoc khi thoi tiet doi
        fired.append("indoor-buffer")
    elif b.get("weather_sensitive") and not a.get("weather_sensitive"):
        margin += 0.2
        fired.append("indoor-buffer")
    return margin, fired


def _rule_margin(a: dict, b: dict) -> tuple[float, list[str]]:
    """Signed margin >0 means a->b beats b->a. Delegates to T027 scorer."""
    if _HAS_RULE_SCORE:
        return _rule_score(a, b), _explain(a, b)
    return _legacy_margin(a, b)


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


def sample_human(pairs: list[dict], n: int = 200, seed: int = 7) -> list[dict]:
    """Stratified sample for the <=3-day human check (post-batch)."""
    rng = random.Random(seed)
    by_label: dict[int, list[dict]] = {1: [], 0: [], -1: []}
    for p in pairs:
        by_label[p["label"]].append(p)
    per = n // 3
    out: list[dict] = []
    for label in (1, 0, -1):
        pool = by_label[label][:]
        rng.shuffle(pool)
        out.extend(pool[:per])
    rng.shuffle(out)
    return out


def emit_judge_batch(pois: list[dict], path: str, n: int = 600, seed: int = 7) -> int:
    """Write judge prompts JSONL (both orders per item = swap-check)."""
    rng = random.Random(seed)
    combos = list(itertools.combinations(sorted(pois, key=lambda p: p["poi_id"]), 2))
    rng.shuffle(combos)
    rows: list[dict] = []
    for a, b in combos[: (n // 2)]:
        for first, second in ((a, b), (b, a)):
            rows.append({
                "prompt": ("Chon thu tu tot hon cho khach thich van dong truoc, "
                           "thu gian sau. Tra JSON {\"choice\": \"first\"|\"second\"|\"tie\"}.\n"
                           f"First: {first['name']} ({first['type']}, "
                           f"rating {first.get('rating')}, tags {first.get('tags')})\n"
                           f"Second: {second['name']} ({second['type']}, "
                           f"rating {second.get('rating')}, tags {second.get('tags')})"),
                "first_id": first["poi_id"], "second_id": second["poi_id"],
            })
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def collect_judge(path: str) -> list[dict]:
    """Parse returned judge JSONL (each line: first_id, second_id, choice)."""
    pairs: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            row = json.loads(line)
            label = {"first": 1, "tie": 0, "second": -1}[row["choice"]]
            pairs.append({"pair_id": f"llm-{i}", "first_id": row["first_id"],
                          "second_id": row["second_id"], "label": label,
                          "margin": 0.0, "source": "llm", "rules": ["llm-judge"],
                          "swapped_from": None})
    return pairs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T028 pair builder")
    ap.add_argument("--snapshot", default="data/snapshots/danang-v1")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="")
    ap.add_argument("--check", default="")
    ap.add_argument("--emit-judge-batch", default="")
    args = ap.parse_args(argv)

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
    if args.emit_judge_batch:
        k = emit_judge_batch(pois, args.emit_judge_batch, n=args.n, seed=args.seed)
        print(f"wrote {k} judge prompts -> {args.emit_judge_batch} (chay Qwen sau, chua co data)")
        return 0

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
