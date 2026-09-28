"""Mobility prior builder (T062 M1, lane A). Foursquare TSMC2014 NYC+TKY.

P(next_cat | prev_cat, time-bucket) with add-k smoothing + held-out
eval (accuracy@1, perplexity) vs unigram baseline. Raw TSVs stay OUT of
the repo (TEMP/local path via --data-dir, never committed).

Buckets (local hour = UTC + tz offset): sang [5,11), trua [11,14),
chieu [14,18), toi otherwise. Transitions = consecutive same-user
check-ins with gap <= 12h; trajectories SPLIT on excluded/unmapped
categories (crosswalk.json). User-level 80/20 split (no leakage).

Usage:
  python BE/ml/patm/build_prior.py --data-dir <tsmc-txt-dir> --out BE/ml/patm/transition_prior.json
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import math
import os
import random
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

BUCKETS = ("sang", "trua", "chieu", "toi")
ADD_K = 1.0
MAX_GAP_H = 12.0


def bucket_of(hour: int) -> str:
    if 5 <= hour < 11:
        return "sang"
    if 11 <= hour < 14:
        return "trua"
    if 14 <= hour < 18:
        return "chieu"
    return "toi"


def load_crosswalk() -> dict:
    with open(os.path.join(os.path.dirname(__file__), "crosswalk.json"),
              encoding="utf-8") as f:
        return json.load(f)


def resolve(cat: str, xw: dict, explicit: dict[str, str]) -> str | None:
    """DN canonical, 'EXCLUDE', or None (unmapped tail -> split)."""
    if cat in explicit:
        return explicit[cat]
    low = cat.lower()
    for kw, target in xw["rules"]:
        if kw in low:
            return target if target != "EXCLUDE" else "EXCLUDE"
    return None


def parse_time(s: str) -> datetime.datetime:
    # "Tue Apr 03 18:00:09 +0000 2012"
    return datetime.datetime.strptime(s.strip(), "%a %b %d %H:%M:%S %z %Y")


def load_sequences(data_dir: str, xw: dict) -> tuple[dict, dict]:
    explicit: dict[str, str] = {}
    for canon, names in xw.items():
        if canon.startswith("_") or canon in ("rules", "excluded"):
            continue
        for n in names:
            explicit[n] = canon
    for n in xw.get("excluded", []):
        explicit[n] = "EXCLUDE"
    users: dict[str, list] = {}
    skipped = {"excluded": 0, "unmapped": 0, "rows": 0}
    for path in sorted(glob.glob(os.path.join(data_dir, "*.txt"))):
        if "readme" in path.lower():
            continue
        # ISO-8859-1: dataset has latin-1 names (Café); utf-8 mangles them
        with open(path, encoding="ISO-8859-1") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) < 8:
                    continue
                skipped["rows"] += 1
                cat = resolve(p[3], xw, explicit)
                if cat == "EXCLUDE":
                    skipped["excluded"] += 1
                    users.setdefault(p[0], []).append(None)  # split marker
                    continue
                if cat is None:
                    skipped["unmapped"] += 1
                    users.setdefault(p[0], []).append(None)
                    continue
                try:
                    utc = parse_time(p[7])
                except ValueError:
                    continue
                local = utc + datetime.timedelta(minutes=int(p[6]))
                users.setdefault(p[0], []).append((local, cat))
    seqs: dict[str, list] = {}
    epoch = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    for u, evs in users.items():
        # Time-ordered walk; None markers (excluded/unmapped) split segments.
        full = sorted(evs, key=lambda e: e[0] if e is not None else epoch)
        cur: list = []
        prev_dt = None
        for e in full:
            if e is None:
                if len(cur) >= 2:
                    seqs.setdefault(u, []).append(cur)
                cur, prev_dt = [], None
                continue
            dt, cat = e
            if prev_dt is not None and (dt - prev_dt).total_seconds() / 3600 > MAX_GAP_H:
                if len(cur) >= 2:
                    seqs.setdefault(u, []).append(cur)
                cur = []
            cur.append((dt, cat))
            prev_dt = dt
        if len(cur) >= 2:
            seqs.setdefault(u, []).append(cur)
    return seqs, skipped


def build(seqs: dict, seed: int = 7) -> dict:
    cats = sorted({c for ss in seqs.values() for s in ss for _, c in s})
    rng = random.Random(seed)
    users = sorted(seqs)
    rng.shuffle(users)
    k = max(1, int(len(users) * 0.2))
    held, train = set(users[:k]), users[k:]
    counts: dict[str, dict[str, dict[str, int]]] = {}
    uni: dict[str, int] = {}
    n_train = n_held = 0
    for u in train:
        for s in seqs[u]:
            for (d1, c1), (d2, c2) in zip(s, s[1:]):
                b = bucket_of(d1.hour)
                counts.setdefault(b, {}).setdefault(c1, {}).setdefault(c2, 0)
                counts[b][c1][c2] += 1
                uni[c2] = uni.get(c2, 0) + 1
                n_train += 1
    trans: dict[str, dict[str, dict[str, float]]] = {}
    for b, d1 in counts.items():
        for c1, d2 in d1.items():
            tot = sum(d2.values()) + ADD_K * len(cats)
            trans.setdefault(b, {})[c1] = {c: (d2.get(c, 0) + ADD_K) / tot
                                           for c in cats}
    tot_u = sum(uni.values())
    unigram = {c: uni.get(c, 0) / tot_u for c in cats}
    # held-out eval
    acc_p = acc_u = 0
    ll_p = ll_u = 0.0
    for u in held:
        for s in seqs[u]:
            for (d1, c1), (d2, c2) in zip(s, s[1:]):
                b = bucket_of(d1.hour)
                pp = trans.get(b, {}).get(c1, {}).get(c2, 1.0 / len(cats))
                pu = unigram.get(c2, 1.0 / len(cats))
                best_p = max(cats, key=lambda c: trans.get(b, {}).get(c1, {}).get(c, 0))
                best_u = max(cats, key=lambda c: unigram.get(c, 0))
                acc_p += best_p == c2
                acc_u += best_u == c2
                ll_p += math.log(pp)
                ll_u += math.log(pu)
                n_held += 1
    return {"cats": cats, "buckets": list(BUCKETS), "add_k": ADD_K,
            "trans": trans, "unigram": unigram,
            "eval": {"n_train": n_train, "n_held": n_held,
                     "acc_prior": acc_p / n_held, "acc_unigram": acc_u / n_held,
                     "ppl_prior": math.exp(-ll_p / n_held),
                     "ppl_unigram": math.exp(-ll_u / n_held)}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T062 mobility prior builder")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", default="BE/ml/patm/transition_prior.json")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)
    xw = load_crosswalk()
    seqs, skipped = load_sequences(args.data_dir, xw)
    print(f"users with seqs: {len(seqs)}, skipped rows/excl/unmapped: {skipped}")
    prior = build(seqs, args.seed)
    ev = prior["eval"]
    gain = (ev["acc_prior"] - ev["acc_unigram"]) / ev["acc_unigram"] if ev["acc_unigram"] else 0
    print(f"held-out n={ev['n_held']}: acc prior {ev['acc_prior']:.4f} vs "
          f"unigram {ev['acc_unigram']:.4f} (rel {gain:+.1%}), "
          f"ppl {ev['ppl_prior']:.2f} vs {ev['ppl_unigram']:.2f}")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(prior, f)
    print(f"wrote -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
