"""Emit judge batch v2: pairs x synthetic user profiles x contexts (lane A).

Personalization features (u_*, c_*) have zero gain because v1 training saw
only neutral defaults. v2 conditions each prompt on a profile + context so
the judge's labels carry preference signal. Same output contract as
make_pairs --emit-judge-batch (prompt, first_id, second_id, both orders).

Profiles (6 archetypes) x contexts (hour/rain) sampled per pair; pairs
stratified over canonical-pair types to cover new cats (spa/bar/lodging/
peak/worship/gift). Deterministic on seed.

Usage: python BE/ml/patm/judge_batch_v2.py --snapshot ... --out C:/tmp/judge_v2.jsonl --n-pairs 150 --seed 7
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
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

from BE.common import load_pois  # noqa: E402
from BE.ml.patm.estimate_duration import canonical_category  # noqa: E402

PROFILES = [
    "gia dinh co tre nho, thich nhe nhang, uu tien trong nha",
    "cap doi hen ho, thich yen tinh, view dep",
    "nhom tre the luc cao, thich van dong manh, leo nui",
    "nguoi lon tuoi, di cham, tranh leo treo",
    "khach tiet kiem, uu tien mien phi, an re",
    "khach chi manh, uu tien trai nghiem cao cap",
]
CONTEXTS = [
    "sang 9h, khong mua",
    "chieu 14h, khong mua",
    "chieu 14h, mua to",
    "toi 19h, khong mua",
]

BASE = ("Chon thu tu tot hon cho khach: {profile}. Boi canh: {ctx}. "
        "Tra JSON {{\"choice\": \"first\"|\"second\"|\"tie\"}}.\n"
        "First: {a} ({ta}, rating {ra}, tags {ga})\n"
        "Second: {b} ({tb}, rating {rb}, tags {gb})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-pairs", type=int, default=150)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    pois = list(load_pois(args.snapshot))
    by_id = {p["poi_id"]: p for p in pois}

    by_tp: dict[str, list] = {}
    for a, b in itertools.combinations(sorted(pois, key=lambda p: p["poi_id"]), 2):
        tp = "|".join(sorted([canonical_category(a.get("type", "")),
                              canonical_category(b.get("type", ""))]))
        by_tp.setdefault(tp, []).append((a, b))
    tps = sorted(by_tp)
    picked = []
    i = 0
    while len(picked) < args.n_pairs and any(by_tp.values()):
        pool = by_tp[tps[i % len(tps)]]
        if pool:
            picked.append(pool.pop(rng.randrange(len(pool))))
        i += 1

    rows = []
    for a, b in picked:
        prof, ctx = rng.choice(PROFILES), rng.choice(CONTEXTS)
        for first, second in ((a, b), (b, a)):
            rows.append({
                "prompt": BASE.format(
                    profile=prof, ctx=ctx, a=first["name"], ta=first["type"],
                    ra=first.get("rating"), ga=first.get("tags"),
                    b=second["name"], tb=second["type"],
                    rb=second.get("rating"), gb=second.get("tags")),
                "first_id": first["poi_id"], "second_id": second["poi_id"],
                "profile": prof, "ctx": ctx,
            })
    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} prompts ({len(picked)} pairs x 2 orders, "
          f"{len(tps)} type-combos) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
