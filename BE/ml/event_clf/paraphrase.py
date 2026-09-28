"""Paraphrase: rule-based variants now, Qwen batch frame for later (T044).

Phase 1 (now, no LLM): slot filling + synonym swaps + light noise
punctuation/case. Phase 2 (when Qwen available): `--emit-qwen-batch`
writes prompts, overnight run, `--collect-qwen` parses JSONL back into
labeled samples (owner: lane A, same pattern as PATM judge batch).
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

from BE.ml.event_clf.templates import (
    EVENT_TYPES,
    SEED_AMOUNTS,
    SEED_DISHES,
    SEED_POIS,
    SEED_TIMES,
    SYNONYMS,
    TEMPLATES,
)

SLOT_POOLS = {"poi": SEED_POIS, "time": SEED_TIMES,
              "dish": SEED_DISHES, "amount": SEED_AMOUNTS}


def fill(template: str, rng: random.Random) -> str:
    out = template
    for slot, pool in SLOT_POOLS.items():
        if "{" + slot + "}" in out:
            out = out.replace("{" + slot + "}", rng.choice(pool))
    return out


def variants(text: str, rng: random.Random, k: int = 3) -> list[str]:
    """Rule-based paraphrases: synonym swaps (+ optional suffix/punct)."""
    outs = [text]
    keys = [w for w in SYNONYMS if w in text]
    for _ in range(k):
        v = text
        for w in keys:
            if rng.random() < 0.5:
                v = v.replace(w, rng.choice(SYNONYMS[w]), 1)
        if rng.random() < 0.3:
            v += rng.choice([" nhé", " giúp mình", " nha", ""])
        if rng.random() < 0.2:
            v = v[0].upper() + v[1:]
        if v != text or not outs[1:]:
            outs.append(v)
    seen = list(dict.fromkeys(outs))
    return seen[: k + 1]


def build_dataset(n_per_class: int = 40, seed: int = 7) -> list[tuple[str, str]]:
    """Balanced (text, label); deterministic on seed."""
    rng = random.Random(seed)
    data: list[tuple[str, str]] = []
    per_template = max(1, n_per_class // max(len(TEMPLATES[t]) for t in EVENT_TYPES))
    for label in EVENT_TYPES:
        made = 0
        for tpl in itertools.cycle(TEMPLATES[label]):
            if made >= n_per_class:
                break
            base = fill(tpl, rng)
            for v in variants(base, rng, k=2):
                if made >= n_per_class:
                    break
                data.append((v, label))
                made += 1
    rng.shuffle(data)
    return data


def emit_qwen_batch(samples: list[tuple[str, str]], path: str) -> int:
    rows = [{"prompt": ("Viết lại 3 cách nói khác nhau, giữ nguyên ý định. "
                        "Trả JSON {\"paraphrases\": [...]}.\nCâu: " + text),
             "label": label} for text, label in samples]
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def collect_qwen(path: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            for p in row["paraphrases"]:
                out.append((p, row["label"]))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T044 paraphrase helper")
    ap.add_argument("--n-per-class", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="")
    ap.add_argument("--emit-qwen-batch", default="")
    args = ap.parse_args(argv)
    data = build_dataset(args.n_per_class, args.seed)
    print(f"built {len(data)} samples / {len(EVENT_TYPES)} classes")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump([{"text": t, "label": l} for t, l in data],
                      f, ensure_ascii=False, indent=1)
        print(f"wrote -> {args.out}")
    if args.emit_qwen_batch:
        k = emit_qwen_batch(data, args.emit_qwen_batch)
        print(f"wrote {k} Qwen prompts -> {args.emit_qwen_batch} (chay sau)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
