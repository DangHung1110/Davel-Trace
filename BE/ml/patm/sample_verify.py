"""Build human-verify set: 200 pairs, disagreement-first (lane A, stdlib).

Priority: rule-vs-LLM disagreements (highest info value), then stratified
sample of agreements/ties across canonical type-pairs. Outputs:
  human_verify_200.md   - checklist for the human (tick A/B/hòa)
  human_verify_200.jsonl - machine rows {first_id, second_id, human: null}
    -> fill "human" with 1/0/-1 and ingest as source=human pairs later.

Usage (repo root):
  python BE/ml/patm/sample_verify.py --snapshot BE/data/snapshots/danang-v1 --rule-pairs C:/tmp/pairs_rule1k.json --llm-out C:/tmp/judge_local.jsonl --n 200
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

from BE.common import load_pois  # noqa: E402
from BE.ml.patm.estimate_duration import canonical_category  # noqa: E402
from BE.ml.patm.make_pairs import collect_judge  # noqa: E402

LBL = {1: "A trước", 0: "hòa", -1: "B trước"}


def one_line(p: dict) -> str:
    st = p.get("smart_tags") or {}
    bits = [p.get("name", "?"), f"({p.get('type', '?')})"]
    if p.get("rating") is not None:
        bits.append(f"★{p['rating']}")
    vm = (p.get("visit_min") or {}).get("p50")
    if vm:
        bits.append(f"~{vm}p")
    if p.get("opening_hours"):
        bits.append("giờ " + ",".join(p["opening_hours"]))
    if st.get("ticket") is True:
        bits.append("có vé" + (f" {p['ticket_vnd']}đ"
                               if p.get("ticket_vnd") else ""))
    return " ".join(bits)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--rule-pairs", required=True)
    ap.add_argument("--llm-out", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    pois = {p["poi_id"]: p for p in load_pois(args.snapshot)}
    from BE.ml.patm.make_pairs import label_ordered as _lab  # noqa: E402
    llm = collect_judge(args.llm_out)
    groups: dict[str, list] = {}
    for p in llm:
        groups.setdefault("|".join(sorted([p["first_id"],
                                           p["second_id"]])), []).append(p)
    # consistent mirrors only (same gate as training)
    agreed_llm = []
    for g, ps in groups.items():
        if len(ps) == 2 and ps[0]["label"] == -ps[1]["label"]:
            agreed_llm.append(ps[0])
        elif len(ps) == 1:
            agreed_llm.append(ps[0])

    # rule label computed on demand (same scorer as training) — no reliance
    # on which pairs a rule file happened to sample.
    disag, agr = [], []
    for p in agreed_llm:
        rl = _lab(pois[p["first_id"]], pois[p["second_id"]])["label"]
        p["_rule"] = rl
        (disag if rl != p["label"] else agr).append(p)

    # stratify agreements by canonical type-pair
    by_tp: dict[str, list] = {}
    for p in agr:
        tp = "|".join(sorted([canonical_category(pois[p["first_id"]]["type"]),
                              canonical_category(pois[p["second_id"]]["type"])]))
        by_tp.setdefault(tp, []).append(p)
    want_dis, want_agr = min(len(disag), args.n * 13 // 20), 0
    want_agr = min(len(agr), args.n - want_dis)
    rng.shuffle(disag)
    pick = disag[:want_dis]
    per_tp = max(1, want_agr // max(1, len(by_tp)))
    rest = []
    for pool in by_tp.values():
        rng.shuffle(pool)
        pick.extend(pool[:per_tp])
        rest.extend(pool[per_tp:])
    rng.shuffle(rest)
    pick.extend(rest[:args.n - len(pick)])
    rng.shuffle(pick)
    pick = pick[:args.n]

    out_dir = args.out_dir or args.snapshot

    def oriented_rule(p):
        return p.get("_rule")

    n_dis = sum(1 for p in pick if oriented_rule(p) not in (None, p["label"]))
    md = [f"# Human verify 200 cặp PATM (disagree-first: {n_dis} cặp cãi nhau)",
          "",
          "Cách tick: sửa `[ ]` thành `[x]` ở đúng 1 ô A/B/hòa mỗi dòng. "
          "A = điểm đầu đi trước hợp lý hơn.",
          "Ưu tiên dòng **CÃI NHAU** (rule và máy chấm khác nhau).",
          ""]
    rows = []
    for i, p in enumerate(pick, 1):
        a, b = pois[p["first_id"]], pois[p["second_id"]]
        rl = oriented_rule(p)
        flag = "CÃI NHAU" if rl is not None and rl != p["label"] else "xem thêm"
        md.append(f"## {i}. [{flag}] {a['name']}  vs  {b['name']}")
        md.append(f"- A: {one_line(a)}")
        md.append(f"- B: {one_line(b)}")
        md.append(f"- máy chấm: {LBL[p['label']]} | rule: {LBL[rl] if rl is not None else '?'}")
        md.append(f"- [ ] A trước | [ ] hòa | [ ] B trước")
        md.append("")
        rows.append({"pair_n": i, "first_id": p["first_id"],
                     "second_id": p["second_id"], "first_name": a["name"],
                     "second_name": b["name"], "rule": rl,
                     "llm": p["label"], "human": None})
    with open(os.path.join(out_dir, "human_verify_200.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(os.path.join(out_dir, "human_verify_200.jsonl"), "w",
              encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} verify pairs "
          f"({sum(1 for r in rows if r['rule'] != r['llm'])} disagreements)"
          f" -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
