"""Merge the raters' exports of plan_pairs.html, map A/B back through the hidden key, and
report how often the raters agree, and how often an LLM judge agrees with them.

    python BE/eval/human/ingest_plan_pairs.py cham_an_*.json cham_binh_*.json
    python BE/eval/human/ingest_plan_pairs.py r1.json r2.json --llm llm.jsonl \
        --out BE/eval/human/plan_pairs_v1_labels.json

Nothing is written without --out, so a trial run never lands in the repo as human labels.

Inputs
- Exports of plan_pairs.html (schema plan-pairs-ratings-v1):
    {"rater", "dataset", "answers": {pair_id: {"choice": "A" | "B" | "tie" | null,
     "tags": {"A": [...], "B": [...]}, "comment", "secs", "at"}}}
  Several exports of one rater merge pair by pair (the later `at` wins). An export of
  another dataset (another set of pairs) is refused.
- The key (plan_pairs_v1_key.json): per pair, the canonical first / second plan and the
  plan shown as A / B.
- LLM labels (--llm, repeatable, one judge per file): a JSON list, {"pairs" | "labels":
  [...]}, or JSON lines. One record per pair, in any of these forms:
    {"pair_id": "P001", "choice": "A" | "B" | "tie"}                  the judge saw A / B
    {"pair_id": "P001", "label": 1 | 0 | -1}                          +1 = the key's first plan
    {"first_id": plan_id, "second_id": plan_id, "label": 1 | 0 | -1}  PATM style, either order
  `winner` / `preferred` work like `choice`. A pair judged more than once (for example
  with A and B swapped) takes the majority, and the report counts the inconsistent ones.

Output (--out): PATM-style records (BE/ml/patm/make_pairs.py), one per pair someone rated:
    {"pair_id", "request_id", "first_id", "second_id", "first_variant", "second_variant",
     "label": +1 / 0 / -1 when every rater agrees (else null), "labels": {rater: label},
     "source": "human", "tags": {rater: {"first": [...], "second": [...]}}, "comments"}
next to the report the command prints.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY_PATH = HERE / "plan_pairs_v1_key.json"
EXPORT_SCHEMA = "plan-pairs-ratings-v1"
LABELS_SCHEMA = "plan-pairs-v1-labels"
CATEGORIES = (1, 0, -1)
CHOICE_WORDS = {"a": "A", "b": "B", "tie": "tie", "ngang": "tie", "ngang nhau": "tie",
                "equal": "tie", "draw": "tie", "=": "tie"}
VARIANT_VI = {"savings": "Tiết kiệm", "balanced": "Cân bằng", "experience": "Trải nghiệm"}
FAST_SECONDS = 10


class IngestError(ValueError):
    """An input that cannot be merged (wrong file, other dataset)."""


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------

def read_records(path: Path) -> list[dict]:
    """JSON list, {"pairs" | "labels" | "records": [...]}, or JSON lines."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(doc, list):
        return doc
    for field in ("pairs", "labels", "records"):
        if isinstance(doc.get(field), list):
            return doc[field]
    raise IngestError(f"{path}: no list of records")


def check_export(doc: dict, dataset: str, name: str = "") -> dict:
    if not isinstance(doc, dict) or doc.get("schema") != EXPORT_SCHEMA or not isinstance(doc.get("answers"), dict):
        raise IngestError(f"{name}: not an export of plan_pairs.html ({EXPORT_SCHEMA})")
    if doc.get("dataset") != dataset:
        raise IngestError(f"{name}: dataset {doc.get('dataset')!r} is not the key's {dataset!r}")
    return doc


def merge_exports(exports: list[dict]) -> dict[str, dict]:
    """{rater: {pair_id: answer}}; one rater's exports merge, the later `at` wins."""
    by_rater: dict[str, dict] = defaultdict(dict)
    for doc in exports:
        rater = str(doc.get("rater") or "").strip() or "?"
        mine = by_rater[rater]
        for pair_id, answer in doc["answers"].items():
            if not isinstance(answer, dict):
                continue
            old = mine.get(pair_id)
            if old is None or (answer.get("at") or "") >= (old.get("at") or ""):
                mine[pair_id] = answer
    return dict(by_rater)


# --------------------------------------------------------------------------
# A / B -> first / second
# --------------------------------------------------------------------------

def side_label(choice: str | None, pair: dict) -> int | None:
    """A rater's choice on the screen -> PATM label of the key's first plan."""
    if choice == "tie":
        return 0
    if choice not in ("A", "B"):
        return None
    shown = pair[choice]
    if shown == pair["first"]:
        return 1
    if shown == pair["second"]:
        return -1
    raise IngestError(f"key: {choice} of a pair is neither its first nor its second plan")


def side_tags(tags: dict | None, pair: dict) -> dict:
    """Tags a rater put on plan A / B -> the same tags on first / second."""
    tags = tags or {}
    out = {"first": [], "second": []}
    for side in ("A", "B"):
        target = "first" if pair[side] == pair["first"] else "second"
        out[target] = list(tags.get(side) or [])
    return out


def human_labels(by_rater: dict[str, dict], key_pairs: dict) -> tuple[dict, Counter]:
    """{rater: {pair_id: label}} for every pair with a choice; unknown pair ids counted."""
    labels, unknown = {}, Counter()
    for rater, answers in by_rater.items():
        mine = {}
        for pair_id, answer in answers.items():
            if pair_id not in key_pairs:
                unknown[rater] += 1
                continue
            label = side_label(answer.get("choice"), key_pairs[pair_id])
            if label is not None:
                mine[pair_id] = label
        labels[rater] = mine
    return labels, unknown


def llm_labels(records: list[dict], key_pairs: dict) -> tuple[dict, Counter]:
    """{pair_id: label} from one judge's records, plus what was skipped and why."""
    by_plans = {frozenset((p["first"], p["second"])): pid for pid, p in key_pairs.items()}
    votes, skipped = defaultdict(list), Counter()
    for rec in records:
        if not isinstance(rec, dict):
            skipped["not a record"] += 1
            continue
        first, second = rec.get("first_id"), rec.get("second_id")
        pair_id = rec.get("pair_id")
        if pair_id not in key_pairs and first and second:
            pair_id = by_plans.get(frozenset((first, second)))
        if pair_id not in key_pairs:
            skipped["pair not in the key"] += 1
            continue
        pair = key_pairs[pair_id]
        word = next((rec[f] for f in ("choice", "winner", "preferred") if rec.get(f) is not None), None)
        if word is None and isinstance(rec.get("label"), str):
            word = rec["label"]
        if word is not None:
            choice = CHOICE_WORDS.get(str(word).strip().lower())
            if choice is None:
                skipped["unreadable choice"] += 1
                continue
            votes[pair_id].append(side_label(choice, pair))
            continue
        try:
            label = int(rec.get("label"))
        except (TypeError, ValueError):
            skipped["no label"] += 1
            continue
        if label not in CATEGORIES:
            skipped["label not -1/0/1"] += 1
            continue
        if first and second:
            if (first, second) == (pair["second"], pair["first"]):
                label = -label
            elif (first, second) != (pair["first"], pair["second"]):
                skipped["plan ids do not match the key"] += 1
                continue
        votes[pair_id].append(label)
    out, inconsistent = {}, 0
    for pair_id, vals in votes.items():
        total = sum(vals)
        out[pair_id] = (total > 0) - (total < 0)
        inconsistent += len(set(vals)) > 1
    skipped["inconsistent pairs (kept, majority)"] = inconsistent
    return out, Counter({k: v for k, v in skipped.items() if v})


# --------------------------------------------------------------------------
# Agreement
# --------------------------------------------------------------------------

def cohen_kappa(x: list[int], y: list[int]) -> float | None:
    """Cohen's kappa of two raters over the same items (None when it is undefined)."""
    n = len(x)
    if n == 0 or n != len(y):
        return None
    po = sum(a == b for a, b in zip(x, y)) / n
    cx, cy = Counter(x), Counter(y)
    pe = sum(cx[c] * cy[c] for c in set(cx) | set(cy)) / (n * n)
    if pe >= 1:
        return None
    return (po - pe) / (1 - pe)


def kappa_se(x: list[int], y: list[int]) -> float | None:
    """Large-sample standard error of kappa, sqrt(po(1-po) / (n (1-pe)^2)) (Cohen 1960)."""
    n = len(x)
    if n == 0:
        return None
    po = sum(a == b for a, b in zip(x, y)) / n
    cx, cy = Counter(x), Counter(y)
    pe = sum(cx[c] * cy[c] for c in set(cx) | set(cy)) / (n * n)
    if pe >= 1:
        return None
    return math.sqrt(po * (1 - po) / (n * (1 - pe) ** 2))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson interval of a proportion k / n."""
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def agreement(lx: dict, ly: dict) -> dict:
    """How two label sets agree on the pairs both labelled."""
    shared = sorted(set(lx) & set(ly))
    x, y = [lx[p] for p in shared], [ly[p] for p in shared]
    n, same = len(shared), sum(a == b for a, b in zip(x, y))
    decisive = [(a, b) for a, b in zip(x, y) if a and b]
    out = {"n": n, "agree": same, "pct": same / n if n else None, "ci": wilson(same, n),
           "kappa": cohen_kappa(x, y), "kappa_se": kappa_se(x, y),
           "decisive_n": len(decisive), "decisive_agree": sum(a == b for a, b in decisive),
           "opposite": sum(a == -b != 0 for a, b in zip(x, y)),
           "confusion": {f"{a}|{b}": c for (a, b), c in sorted(Counter(zip(x, y)).items())}}
    out["decisive_pct"] = out["decisive_agree"] / len(decisive) if decisive else None
    return out


def consensus(labels: dict[str, dict]) -> dict:
    """{pair_id: label | None}: the label when every rater who rated it agrees."""
    votes = defaultdict(list)
    for mine in labels.values():
        for pair_id, label in mine.items():
            votes[pair_id].append(label)
    return {pid: (vals[0] if len(set(vals)) == 1 else None) for pid, vals in votes.items()}


def variant_wins(labels: dict, key_pairs: dict) -> dict:
    """Per pair of variants, how often the first won, tied, or lost."""
    out = defaultdict(lambda: {"first": 0, "tie": 0, "second": 0})
    for pair_id, label in labels.items():
        if label is None:
            continue
        pair = key_pairs[pair_id]
        combo = f"{pair['variants'][pair['first']]}|{pair['variants'][pair['second']]}"
        out[combo][{1: "first", 0: "tie", -1: "second"}[label]] += 1
    return dict(sorted(out.items()))


def rater_habits(answers: dict, key_pairs: dict) -> dict:
    """Which side a rater picks (a strong lean to A or B is a habit, not a taste), how
    long a pair took, and how many went by in under FAST_SECONDS."""
    choices = Counter(a.get("choice") for pid, a in answers.items() if pid in key_pairs and a.get("choice"))
    secs = [a["secs"] for a in answers.values() if isinstance(a.get("secs"), (int, float)) and a.get("choice")]
    return {"rated": sum(choices.values()), "A": choices["A"], "B": choices["B"], "tie": choices["tie"],
            "median_secs": statistics.median(secs) if secs else None,
            "fast": sum(s < FAST_SECONDS for s in secs)}


def tag_counts(by_rater: dict, key_pairs: dict, labels: dict) -> dict:
    """Tags on the plan the rater preferred vs the other one (ties left out)."""
    out = {"preferred": Counter(), "other": Counter()}
    for rater, answers in by_rater.items():
        for pair_id, answer in answers.items():
            label = labels.get(rater, {}).get(pair_id)
            if pair_id not in key_pairs or not label:
                continue
            tags = side_tags(answer.get("tags"), key_pairs[pair_id])
            win, lose = ("first", "second") if label == 1 else ("second", "first")
            out["preferred"].update(tags[win])
            out["other"].update(tags[lose])
    return {k: dict(v.most_common()) for k, v in out.items()}


# --------------------------------------------------------------------------
# Putting it together
# --------------------------------------------------------------------------

def ingest(key: dict, exports: list[dict], judges: dict[str, list[dict]] | None = None) -> dict:
    """Everything the command prints and writes, from loaded documents."""
    key_pairs = key["pairs"]
    for doc in exports:
        check_export(doc, key["dataset"], str(doc.get("rater") or "?"))
    by_rater = merge_exports(exports)
    labels, unknown = human_labels(by_rater, key_pairs)
    agreed = consensus(labels)
    report = {
        "dataset": key["dataset"], "n_pairs": len(key_pairs),
        "raters": {r: rater_habits(by_rater[r], key_pairs) for r in sorted(by_rater)},
        "unknown_pairs": dict(unknown),
        "pairs_of_raters": {f"{a}|{b}": agreement(labels[a], labels[b])
                            for a, b in combinations(sorted(labels), 2)},
        "consensus_n": sum(v is not None for v in agreed.values()),
        "wins": {"consensus": variant_wins(agreed, key_pairs),
                 **{r: variant_wins(labels[r], key_pairs) for r in sorted(labels)}},
        "tags": tag_counts(by_rater, key_pairs, labels),
        "judges": {},
    }
    for name, records in (judges or {}).items():
        judged, skipped = llm_labels(records, key_pairs)
        report["judges"][name] = {
            "labelled": len(judged), "skipped": dict(skipped),
            "vs": {**{r: agreement(judged, labels[r]) for r in sorted(labels)},
                   "consensus": agreement(judged, {k: v for k, v in agreed.items() if v is not None})},
            "wins": variant_wins(judged, key_pairs),
        }
    records = []
    for pair_id in sorted(agreed):
        pair = key_pairs[pair_id]
        records.append({
            "pair_id": pair_id, "request_id": pair["request_id"],
            "first_id": pair["first"], "second_id": pair["second"],
            "first_variant": pair["variants"][pair["first"]], "second_variant": pair["variants"][pair["second"]],
            "label": agreed[pair_id], "labels": {r: labels[r][pair_id] for r in sorted(labels) if pair_id in labels[r]},
            "source": "human",
            "tags": {r: side_tags(by_rater[r][pair_id].get("tags"), pair) for r in sorted(by_rater)
                     if pair_id in by_rater[r]},
            "comments": {r: by_rater[r][pair_id]["comment"] for r in sorted(by_rater)
                         if (by_rater[r].get(pair_id) or {}).get("comment")},
        })
    return {"schema": LABELS_SCHEMA, "dataset": key["dataset"], "label_convention": key.get("label_convention"),
            "raters": sorted(by_rater), "pairs": records, "report": report}


# --------------------------------------------------------------------------
# The printed report (Vietnamese, for the team)
# --------------------------------------------------------------------------

def _pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.0f}%"


def _kappa_word(k: float | None) -> str:
    """Landis & Koch (1977) bands, in plain words."""
    if k is None:
        return "không tính được"
    if k < 0:
        return "kém hơn đoán bừa"
    for limit, word in ((0.2, "rất thấp"), (0.4, "thấp"), (0.6, "vừa phải"), (0.8, "khá cao")):
        if k <= limit:
            return word
    return "rất cao"


def _agreement_lines(a: dict, indent: str = "  ") -> list[str]:
    if not a["n"]:
        return [f"{indent}chưa có cặp nào chung"]
    lo, hi = a["ci"]
    kappa = "–" if a["kappa"] is None else f"{a['kappa']:.2f}"
    se = f" (±{1.96 * a['kappa_se']:.2f})" if a["kappa_se"] is not None else ""
    lines = [f"{indent}giống nhau {a['agree']}/{a['n']} cặp = {_pct(a['pct'])} "
             f"(khoảng tin cậy 95%: {_pct(lo)}–{_pct(hi)}, tức ±{50 * (hi - lo):.0f} điểm)",
             f"{indent}Cohen's kappa {kappa}{se}: {_kappa_word(a['kappa'])}"]
    if a["decisive_n"]:
        lines.append(f"{indent}khi cả hai cùng chọn hẳn một bên ({a['decisive_n']} cặp): cùng bên "
                     f"{_pct(a['decisive_pct'])}; ngược hẳn nhau (một A, một B): {a['opposite']} cặp")
    return lines


def _wins_lines(wins: dict, indent: str = "  ") -> list[str]:
    lines = []
    for combo, w in wins.items():
        first, second = (VARIANT_VI.get(v, v) for v in combo.split("|"))
        total = sum(w.values())
        lines.append(f"{indent}{first} vs {second}: {first} thắng {w['first']}, ngang {w['tie']}, "
                     f"{second} thắng {w['second']} (trên {total} cặp)")
    return lines


def format_report(result: dict) -> str:
    rep = result["report"]
    out = [f"Bộ cặp {rep['dataset']} ({rep['n_pairs']} cặp)", "", "Người chấm:"]
    for rater, h in rep["raters"].items():
        n = h["rated"] or 1
        speed = f"trung vị {h['median_secs']:.0f} giây/cặp" if h["median_secs"] is not None else "chưa có thời gian"
        out.append(f"  {rater}: chấm {h['rated']} cặp · chọn A {_pct(h['A'] / n)}, B {_pct(h['B'] / n)}, "
                   f"ngang {_pct(h['tie'] / n)} · {speed} · {h['fast']} cặp dưới {FAST_SECONDS} giây")
    for rater, n in rep["unknown_pairs"].items():
        out.append(f"  ({rater}: {n} câu trả lời cho cặp không có trong key, đã bỏ qua)")
    for name, a in rep["pairs_of_raters"].items():
        out += ["", f"{' và '.join(name.split('|'))} cùng chấm:"] + _agreement_lines(a)
    if rep["wins"]["consensus"]:
        out += ["", f"Kết luận chung ({rep['consensus_n']} cặp mọi người đồng ý), lịch nào thắng:"]
        out += _wins_lines(rep["wins"]["consensus"])
    tags = rep["tags"]
    if tags["preferred"] or tags["other"]:
        out += ["", "Nhãn hay dùng (trên lịch được chọn / lịch còn lại):"]
        keys = sorted(set(tags["preferred"]) | set(tags["other"]),
                      key=lambda k: -(tags["preferred"].get(k, 0) + tags["other"].get(k, 0)))
        out.append("  " + ", ".join(f"{k} {tags['preferred'].get(k, 0)}/{tags['other'].get(k, 0)}" for k in keys))
    for name, judge in rep["judges"].items():
        out += ["", f"Giám khảo LLM '{name}': có nhãn cho {judge['labelled']} cặp"]
        for reason, n in judge["skipped"].items():
            out.append(f"  ({reason}: {n})")
        for who, a in judge["vs"].items():
            target = "kết luận chung" if who == "consensus" else who
            out.append(f"  so với {target}:")
            out += _agreement_lines(a, "    ")
        out.append("  LLM chọn:")
        out += _wins_lines(judge["wins"], "    ")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exports", nargs="+", type=Path, help="exports of plan_pairs.html")
    ap.add_argument("--key", type=Path, default=KEY_PATH)
    ap.add_argument("--llm", type=Path, action="append", default=[], help="LLM labels (JSON or JSON lines)")
    ap.add_argument("--out", type=Path, default=None, help="write the merged labels and the report here")
    args = ap.parse_args(argv)
    try:
        key = json.loads(args.key.read_text(encoding="utf-8"))
        exports = []
        for path in args.exports:
            doc = json.loads(path.read_text(encoding="utf-8"))
            exports.append(check_export(doc, key["dataset"], str(path)))
        judges = {path.stem: read_records(path) for path in args.llm}
        result = ingest(key, exports, judges)
    except (IngestError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(format_report(result))
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out} ({len(result['pairs'])} pairs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
