"""Event classifier trainer S2 (T044, lane A). TF-IDF + LightGBM, CPU-only.

Why not PhoBERT: 10 short-text classes separate cleanly on word/bigram
signals (template phase); PhoBERT adds GPU/tokenizer weight for no
needed gain — revisit only if LLM-paraphrased data drops macro-F1 < 0.8.

Pipeline: paraphrase.build_dataset -> word 1-2gram TF-IDF (min_df 2,
max 800 feats, sublinear tf) -> stratified 80/20 split -> LightGBM
multiclass -> accuracy + per-class P/R/F1 -> export model.txt +
vocab.json + labels.json. Served later by lane B T046 via
`predict(text)` (loads artifacts once).

Usage:
  python BE/ml/event_clf/train.py --n-per-class 40 --model-dir <TEMP> --seed 7
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.ml.event_clf.paraphrase import build_dataset  # noqa: E402
from BE.ml.event_clf.templates import EVENT_TYPES  # noqa: E402

LABELS = list(EVENT_TYPES)


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def ngrams(tokens: list[str]) -> list[str]:
    out = list(tokens)
    out.extend(a + " " + b for a, b in zip(tokens, tokens[1:]))
    return out


class Tfidf:
    def __init__(self, max_features: int = 800, min_df: int = 2):
        self.max_features = max_features
        self.min_df = min_df
        self.vocab: dict[str, int] = {}
        self.idf: list[float] = []

    def fit(self, texts: list[str]) -> "Tfidf":
        df: dict[str, int] = {}
        for t in texts:
            for g in set(ngrams(tokenize(t))):
                df[g] = df.get(g, 0) + 1
        kept = sorted(((c, g) for g, c in df.items() if c >= self.min_df),
                      reverse=True)[: self.max_features]
        self.vocab = {g: i for i, (_, g) in enumerate(kept)}
        n = len(texts)
        self.idf = [math.log((1 + n) / (1 + df[g])) + 1.0
                    for _, g in kept]
        return self

    def transform(self, texts: list[str]) -> list[list[float]]:
        import numpy as np
        mat = np.zeros((len(texts), len(self.vocab)))
        for r, t in enumerate(texts):
            tf: dict[int, float] = {}
            for g in ngrams(tokenize(t)):
                if g in self.vocab:
                    tf[self.vocab[g]] = tf.get(self.vocab[g], 0.0) + 1.0
            for i, c in tf.items():
                mat[r, i] = (1.0 + math.log(c)) * self.idf[i]
        return mat

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"vocab": self.vocab, "idf": self.idf}, f, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "Tfidf":
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        v = cls()
        v.vocab, v.idf = d["vocab"], d["idf"]
        return v


def stratified_split(data: list, seed: int, frac: float = 0.2) -> tuple[list, list]:
    rng = random.Random(seed)
    by_label: dict[str, list] = {}
    for row in data:
        by_label.setdefault(row[1], []).append(row)
    train, test = [], []
    for rows in by_label.values():
        rng.shuffle(rows)
        k = max(1, int(len(rows) * frac))
        test.extend(rows[:k])
        train.extend(rows[k:])
    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


def prf(y_true: list[int], y_pred: list[int], k: int) -> tuple[float, float, float]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == p == k)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != k and p == k)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == k and p != k)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return prec, rec, f1


def train_eval(texts: list[str], labels: list[str], seed: int,
               model_dir: str) -> dict:
    import lightgbm as lgb
    import numpy as np

    data = list(zip(texts, labels))
    train, test = stratified_split(data, seed)
    vec = Tfidf().fit([t for t, _ in train])
    Xtr, ytr = vec.transform([t for t, _ in train]), \
        np.array([LABELS.index(l) for _, l in train])
    Xte, yte = vec.transform([t for t, _ in test]), \
        np.array([LABELS.index(l) for _, l in test])

    dtr = lgb.Dataset(Xtr, ytr)
    params = {"objective": "multiclass", "num_class": len(LABELS),
              "verbosity": -1, "seed": seed,
              "min_data_in_leaf": 1, "num_leaves": 15}
    bst = lgb.train(params, dtr, num_boost_round=100)
    pred = [int(v) for v in np.argmax(bst.predict(Xte), axis=1)]
    yt = [int(v) for v in yte]

    per_class, f1s = {}, []
    for i, name in enumerate(LABELS):
        p, r, f = prf(yt, pred, i)
        per_class[name] = {"p": round(p, 3), "r": round(r, 3), "f1": round(f, 3)}
        f1s.append(f)
    os.makedirs(model_dir, exist_ok=True)
    bst.save_model(os.path.join(model_dir, "model.txt"))
    vec.save(os.path.join(model_dir, "vocab.json"))
    with open(os.path.join(model_dir, "labels.json"), "w", encoding="utf-8") as f:
        json.dump(LABELS, f, ensure_ascii=False)
    return {"acc": round(sum(a == b for a, b in zip(yt, pred)) / len(yt), 4),
            "n_train": len(train), "n_test": len(test),
            "macro_f1": round(sum(f1s) / len(f1s), 4),
            "min_f1": round(min(f1s), 4),
            "per_class": per_class, "model_dir": model_dir}


def predict(text: str, model_dir: str, _cache: dict = {}) -> str:
    """Load-once inference for lane B T046 (same artifacts as train)."""
    import numpy as np
    if "bst" not in _cache or _cache.get("dir") != model_dir:
        import lightgbm as lgb
        _cache.update(bst=lgb.Booster(model_file=os.path.join(model_dir, "model.txt")),
                      vec=Tfidf.load(os.path.join(model_dir, "vocab.json")),
                      dir=model_dir)
    probs = _cache["bst"].predict(_cache["vec"].transform([text]))
    return LABELS[int(np.argmax(probs))]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T044 event clf trainer")
    ap.add_argument("--n-per-class", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--model-dir", default=os.path.join("BE", "ml", "event_clf"))
    args = ap.parse_args(argv)
    data = build_dataset(args.n_per_class, args.seed)
    rep = train_eval([t for t, _ in data], [l for _, l in data],
                     args.seed, args.model_dir)
    print(f"train {rep['n_train']} / test {rep['n_test']} — "
          f"acc {rep['acc']} macro-F1 {rep['macro_f1']} min-F1 {rep['min_f1']}")
    for name, m in rep["per_class"].items():
        print(f"  {name:12s} P {m['p']:.3f} R {m['r']:.3f} F1 {m['f1']:.3f}")
    print(f"artifacts -> {rep['model_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
