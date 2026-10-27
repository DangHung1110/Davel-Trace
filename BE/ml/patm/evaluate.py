"""POI-disjoint evaluation for PATM with a human-labeled blind subset.

Pairs touching any held-out POI are excluded from training. Only human,
decisive labels in that set are scored; ties are reported separately.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from BE.common import load_json, load_pois
from BE.ml.patm.features import FEATURE_NAMES, extract
from BE.ml.patm.make_pairs import leave_poi_out_split, label_ordered
from BE.ml.patm.train import build_rows


def evaluate(pairs: list[dict], pois: dict, seed: int = 7,
             held_frac: float = 0.2) -> dict:
    import lightgbm as lgb
    import numpy as np

    train_pairs, eval_pairs, leaked = leave_poi_out_split(pairs, held_frac, seed)
    if leaked:
        raise ValueError(f"POI leakage in train split: {leaked[:5]}")
    X, y, _, dropped_ties = build_rows(pois, train_pairs)
    if not X or len(set(y)) < 2:
        raise ValueError("Training split needs both decisive label classes")

    model = lgb.train(
        {"objective": "binary", "verbosity": -1, "seed": seed,
         "min_data_in_leaf": 1, "num_leaves": 7},
        lgb.Dataset(np.asarray(X, dtype=float), label=np.asarray(y, dtype=float)),
        num_boost_round=50,
    )
    human_eval = [p for p in eval_pairs if p.get("source") == "human"]
    decisive = [p for p in human_eval if p["label"] != 0]
    if any(p["first_id"] not in pois or p["second_id"] not in pois for p in decisive):
        raise ValueError("Evaluation pair references a POI missing from snapshot")

    model_correct = rule_correct = 0
    for pair in decisive:
        a, b = pois[pair["first_id"]], pois[pair["second_id"]]
        features = np.asarray([extract(a, b)], dtype=float)
        pred = 1 if model.predict(features)[0] > 0.5 else -1
        model_correct += pred == pair["label"]
        rule_correct += label_ordered(a, b)["label"] == pair["label"]
    n = len(decisive)
    return {
        "protocol": "leave-poi-out; score human decisive labels only; ties excluded",
        "seed": seed, "held_frac": held_frac,
        "poi_count": len({p[k] for p in pairs for k in ("first_id", "second_id")}),
        "train_pair_rows": len(train_pairs), "trainable_rows": len(X),
        "train_ties_dropped": dropped_ties, "eval_pair_rows": len(eval_pairs),
        "eval_human_pairs": len(human_eval), "eval_human_decisive": n,
        "eval_human_ties": len(human_eval) - n,
        "human_label_mix": {str(label): sum(p["label"] == label for p in human_eval)
                            for label in (1, -1, 0)},
        "heldout_poi_count": len({poi_id for p in eval_pairs for poi_id in
                                   (p["first_id"], p["second_id"])} -
                                  {poi_id for p in train_pairs for poi_id in
                                   (p["first_id"], p["second_id"])}),
        "poi_leakage": leaked,
        "feature_count": len(FEATURE_NAMES),
        "model_accuracy": model_correct / n if n else None,
        "model_correct": model_correct,
        "rule_accuracy": rule_correct / n if n else None,
        "rule_correct": rule_correct,
        "warning": "Small human holdout; descriptive only, not a stable quality estimate.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--held-frac", type=float, default=0.2)
    ap.add_argument("--out", default="BE/ml/patm/lpo_metrics.json")
    args = ap.parse_args()
    metrics = evaluate(load_json(args.pairs), load_pois(args.snapshot, by_id=True),
                       args.seed, args.held_frac)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
