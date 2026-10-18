"""LightGBM pairwise trainer, nac-2 (T029-TRAINER, lane A). Smoke-ready.

Formulation: Bradley-Terry-via-logistic — ordered pair (a,b) becomes one
row of DIFFERENCE features F(a)-F(b); target y=1 if a preferred (label 1),
y=0 if b preferred (label -1); ties dropped from training (counted in the
report). Research R2's lambdarank-with-query-groups is the upgrade path
on full data; binary logistic is exact-equivalent for 2-doc groups and
robust on CPU in seconds.

Anti-leakage: mirror orders of one unordered pair share a group id; folds
and held-out split on GROUPS, never rows (else the flip twin leaks).

Pipeline: pairs (make_pairs.py) -> diff features -> 5-fold CV over groups
-> held-out eval (pairwise acc + flip consistency) -> export model.txt
-> metrics JSON next to the model.

Features: T026 `features.py` (16) + T062 mobility prior (17th), ordered-pair input.
User/ctx default to neutral (spec: full-data runs pass real trip context).

Usage:
  python BE/ml/patm/make_pairs.py --snapshot data/snapshots/danang-v1 --n 42 --out /tmp/pairs.json
  python BE/ml/patm/train.py --pairs /tmp/pairs.json --snapshot data/snapshots/danang-v1 --model-out /tmp/model.txt
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.common import load_json, load_pois  # noqa: E402
from BE.ml.patm.features import FEATURE_NAMES, extract  # T026 + T062 (17 features)


def build_rows(pois: dict, pairs: list[dict]) -> tuple[list, list, list]:
    """Return (X, y, groups); ties dropped. Group = unordered pair key."""
    X, y, groups = [], [], []
    dropped_ties = 0
    for p in pairs:
        if p["label"] == 0:
            dropped_ties += 1
            continue
        a, b = pois[p["first_id"]], pois[p["second_id"]]
        X.append(extract(a, b))
        y.append(1 if p["label"] == 1 else 0)
        groups.append("|".join(sorted((p["first_id"], p["second_id"]))))
    return X, y, groups, dropped_ties


def split_groups(groups: list[str], seed: int, held_frac: float = 0.2,
                 folds: int = 5) -> tuple[list[str], list[list[str]]]:
    rng = random.Random(seed)
    uniq = sorted(set(groups))
    rng.shuffle(uniq)
    k = max(1, int(len(uniq) * held_frac))
    held = set(uniq[:k])
    rest = uniq[k:]
    fold_of = [rest[i::folds] for i in range(folds)]
    return sorted(held), fold_of


def train_eval(X, y, groups, seed: int, model_out: str) -> dict:
    import lightgbm as lgb
    import numpy as np

    Xn = np.array(X, dtype=float)
    yn = np.array(y, dtype=float)

    held, fold_of = split_groups(groups, seed)
    te_idx = [i for i, g in enumerate(groups) if g in held]
    tr_idx = [i for i, g in enumerate(groups) if g not in held]

    params = {"objective": "binary", "verbosity": -1, "seed": seed,
              "min_data_in_leaf": 1, "num_leaves": 7}
    # 5-fold CV accuracy (group-wise, no mirror leakage)
    cv_accs = []
    for f in range(len(fold_of)):
        va_groups = set(fold_of[f])
        tri = [i for i in tr_idx if groups[i] not in va_groups]
        vai = [i for i in tr_idx if groups[i] in va_groups]
        if not tri or not vai:
            continue
        dtr = lgb.Dataset(Xn[tri], yn[tri])
        dva = lgb.Dataset(Xn[vai], yn[vai], reference=dtr)
        bst = lgb.train(params, dtr, num_boost_round=50,
                        valid_sets=[dva])
        pred = [1 if v > 0.5 else 0 for v in bst.predict(Xn[vai])]
        cv_accs.append(sum(p == yn[i] for p, i in zip(pred, vai)) / len(vai))

    dtr = lgb.Dataset(Xn[tr_idx], yn[tr_idx])
    bst = lgb.train(params, dtr, num_boost_round=50)
    bst.save_model(model_out)

    # held-out: pairwise acc + flip consistency (pred(x) vs pred(-x))
    pred = bst.predict(Xn[te_idx]) if te_idx else []
    pred_lab = [1 if v > 0.5 else 0 for v in pred]
    acc = (sum(p == yn[i] for p, i in zip(pred_lab, te_idx)) / len(te_idx)) if te_idx else 0.0
    flip_bad = 0
    for i in te_idx:
        neg = -Xn[i]
        if (bst.predict(neg.reshape(1, -1))[0] > 0.5) == (bst.predict(Xn[i].reshape(1, -1))[0] > 0.5):
            flip_bad += 1
    flip = (len(te_idx) - flip_bad) / len(te_idx) if te_idx else 0.0
    return {"cv_acc": sum(cv_accs) / len(cv_accs) if cv_accs else 0.0,
            "cv_folds": len(cv_accs),
            "held_acc": acc, "held_n": len(te_idx),
            "flip_consistency": flip, "model": model_out}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T029 PATM trainer (smoke-ready)")
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--model-out", default="BE/ml/patm/model.txt")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    pois = load_pois(args.snapshot, by_id=True)
    pairs = load_json(args.pairs)
    X, y, groups, dropped = build_rows(pois, pairs)
    print(f"rows: {len(X)} trainable ({dropped} ties dropped), "
          f"{len(set(groups))} unordered groups, {len(FEATURE_NAMES)} features")
    if not X:
        print("no trainable rows — nothing to do")
        return 2
    metrics = train_eval(X, y, groups, args.seed, args.model_out)
    print(f"5-fold CV acc: {metrics['cv_acc']:.3f} ({metrics['cv_folds']} folds)")
    print(f"held-out acc: {metrics['held_acc']:.3f} (n={metrics['held_n']})")
    print(f"flip consistency: {metrics['flip_consistency']:.3f}")
    print(f"model -> {metrics['model']}")
    with open(os.path.splitext(args.model_out)[0] + "_metrics.json", "w",
              encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
