"""Offline LLM-assisted candidate curation (test-local evidence, NOT runtime).

Why: the snapshot's `cat`/`type` labels are rule-derived, so the planner can
offer a seafood lover a vegan restaurant or a BBQ house. The deterministic
ranker only sees tags/rating; a one-shot LLM pass can flag "miscategorized"
or "taste-mismatched" candidates so a human can review them. This is DATA
CURATION EVIDENCE for the request path — the output report is never applied
automatically (no POI/verified flag is mutated, no matrix cell is touched).

Pipeline:
1. load the snapshot and build the SAME candidate pool the planner sees
   (`retrieval.retrieve` over the trip profile: verified + not avoided);
2. send ONE prompt with id/name/type/cat/tags/rating per candidate;
3. normalise the JSON answer to `{poi_id: {keep, drop, reason}}`, report
   unknown/missing ids instead of inventing decisions;
4. write a JSON report + print a short summary.

Usage (repo root):
    python BE/ml/data/curate_pool.py --tag seafood --food-pref "hải sản"
    python BE/ml/data/curate_pool.py --tag seafood --food-pref "hải sản" \
        --out /tmp/curation.json --dry-run          # prompt + pool only
    LLM_PROVIDER=api LLM_API_URL=http://127.0.0.1:1234/v1 \
        LLM_API_MODEL=qwen3-8b python BE/ml/data/curate_pool.py ...

The prompt ends with `/no_think`: qwen3 thinking mode is slow and hangs this
box (same contract as parser.py / review.py). JSON examples use double quotes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.config import get_settings  # noqa: E402
from BE.app.services import llm as llm_gateway  # noqa: E402
from BE.app.services import retrieval as retrieval_svc  # noqa: E402

DEFAULT_SNAPSHOT = os.path.join("BE", "data", "snapshots", "danang-v1")
# An 8B local model needs minutes for a ~3k-token prompt + long JSON; the
# request path keeps its own 120 s budget (this tool is offline only).
CURATION_TIMEOUT_S = 900

PROMPT = (
    "Bạn rà soát dữ liệu địa điểm cho lịch trình du lịch Đà Nẵng.\n"
    "Sở thích ăn uống (food_prefs): {food_prefs}\n"
    "Hoạt động (activities): {activities}\n"
    "Cần tránh (must_avoid): {avoid}\n"
    "Nhiệm vụ: chỉ liệt kê các địa điểm NÊN LOẠI khỏi pool ứng viên, "
    "tối đa 12 địa điểm.\n"
    "Quy tắc loại:\n"
    "- sai loại (miscategorized: tên/loại không khớp cat);\n"
    "- lệch khẩu vị rõ ràng (ví dụ người dùng chỉ thích hải sản mà quán "
    "chay/thịt nướng/BBQ);\n"
    "- thuộc must_avoid.\n"
    "Địa điểm không phải ăn uống (bãi biển, chợ, bảo tàng, di tích) thì "
    "GIỮ nếu đúng loại. Quán hải sản thì GIỮ.\n"
    "KHÔNG bịa địa điểm mới, KHÔNG đổi poi_id, KHÔNG liệt kê địa điểm giữ.\n"
    "Ví dụ (chỉ để hiểu quy tắc, không chép id):\n"
    '- "Hải sản A" (cat=restaurant, tags=Hải sản) -> GIỮ, không liệt kê.\n'
    '- "Nhà hàng chay B" (cat=restaurant, tags=Chay) -> LOẠI, '
    '{{"poi_id": "id_cua_B", "reason": "quán chay, không khớp hải sản"}}.\n'
    "Chỉ trả JSON đúng dạng:\n"
    '{{"drop": [{{"poi_id": "...", "reason": "ly do ngan"}}]}}\n'
    "Nếu không loại địa điểm nào, trả {{\"drop\": []}}.\n"
    "Danh sách địa điểm:\n{candidates}\n"
    "/no_think"
)


def load_candidates(snapshot_dir: str, profile: dict) -> tuple[list[dict], dict]:
    """(verified candidates the planner would see, retrieval report counts)."""
    pois = retrieval_svc.load_pois_json(os.path.join(snapshot_dir, "pois.json"))
    by_id = {p["poi_id"]: p for p in pois}
    found = retrieval_svc.retrieve(profile, pois)
    candidates = [by_id[c["poi_id"]] for c in found["candidates"]]
    counts = {"verified_total": sum(1 for p in pois if p.get("verified")),
              "candidates": len(candidates),
              "needs_verification": len(found["needs_verification"]),
              "excluded": len(found["excluded"])}
    return candidates, counts


def _candidate_lines(candidates: list[dict]) -> str:
    rows = []
    for p in candidates:
        tags = ", ".join(p.get("tags") or [])[:80]
        rows.append(f"- {p['poi_id']} | {p.get('name', '?')} | "
                    f"type={p.get('type', '?')} | cat={p.get('cat', '?')} | "
                    f"tags={tags or '-'} | rating={p.get('rating')}")
    return "\n".join(rows)


def build_prompt(candidates: list[dict], profile: dict) -> str:
    return PROMPT.format(
        food_prefs=", ".join(profile.get("food_prefs") or []) or "(khong co)",
        activities=", ".join(profile.get("activities") or []) or "(khong co)",
        avoid=", ".join(profile.get("must_avoid") or []) or "(khong co)",
        candidates=_candidate_lines(candidates))


def normalize(obj: dict, candidates: list[dict]) -> dict:
    """LLM JSON -> {poi_id: {keep, drop, reason}} + unknown/missing ids.

    Two accepted shapes:
    - {"drop": [{poi_id, reason}]} (primary, compact: a small local model
      writes far less and is less likely to truncate); every candidate the
      model did not name is a keep — that is the prompt's contract, and the
      report says so in the reason.
    - {"decisions": [{poi_id, keep, reason}]} (explicit, also tolerated).
    Unknown ids are reported, never merged. In the explicit shape a candidate
    the model skipped is reported under `missing_ids` with NO decision.
    """
    known = {p["poi_id"] for p in candidates}
    unknown: list[str] = []

    def _items(raw) -> list[dict]:
        if isinstance(raw, dict):  # tolerate {poi_id: value}
            return [{"poi_id": pid, **(v if isinstance(v, dict) else {})}
                    for pid, v in raw.items()]
        return [i for i in raw if isinstance(i, dict)] if isinstance(raw, list) else []

    if obj.get("decisions") is not None:
        decisions: dict[str, dict] = {}
        for item in _items(obj.get("decisions")):
            pid = str(item.get("poi_id") or "").strip()
            if pid not in known:
                unknown.append(pid or "(empty)")
                continue
            keep = item.get("keep")
            if not isinstance(keep, bool):
                keep = str(item.get("drop", "")).strip().lower() not in ("true", "1", "yes")
            decisions[pid] = {"keep": keep, "drop": not keep,
                              "reason": str(item.get("reason") or "").strip()[:200]}
        return {"decisions": decisions, "unknown_ids": unknown,
                "missing_ids": sorted(known - set(decisions)),
                "response_shape": "decisions"}

    flagged: dict[str, str] = {}
    for item in _items(obj.get("drop")):
        pid = str(item.get("poi_id") or "").strip()
        if pid not in known:
            unknown.append(pid or "(empty)")
            continue
        flagged[pid] = str(item.get("reason") or "").strip()[:200]
    decisions = {
        pid: ({"keep": False, "drop": True, "reason": flagged[pid]}
              if pid in flagged else
              {"keep": True, "drop": False,
               "reason": "khong bi flag (LLM chi liet ke diem loai)"})
        for pid in known
    }
    return {"decisions": decisions, "unknown_ids": unknown,
            "missing_ids": [], "response_shape": "drop_list"}


def curate(candidates: list[dict], profile: dict, *, complete=None,
           tag: str = "curation", snapshot: str = "") -> dict:
    """One LLM call -> report dict (never mutates the snapshot)."""
    complete = complete or (
        lambda prompt: llm_gateway.complete_json(
            prompt, timeout_s=CURATION_TIMEOUT_S))
    settings = get_settings()
    prompt = build_prompt(candidates, profile)
    t0 = time.monotonic()
    obj = complete(prompt)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    normalised = normalize(obj, candidates)
    by_id = {p["poi_id"]: p for p in candidates}
    drops = [{"poi_id": pid, "name": by_id[pid].get("name"),
              "type": by_id[pid].get("type"), "cat": by_id[pid].get("cat"),
              "reason": d["reason"]}
             for pid, d in normalised["decisions"].items() if d["drop"]]
    return {
        "tag": tag,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot": snapshot,
        "provider": settings.llm_provider,
        "model": (os.environ.get("LLM_API_MODEL") if settings.llm_provider == "api"
                  else settings.judge_model),
        "profile": profile,
        "candidate_count": len(candidates),
        "decisions": normalised["decisions"],
        "drops": drops,
        "unknown_ids": normalised["unknown_ids"],
        "missing_ids": normalised["missing_ids"],
        "response_shape": normalised["response_shape"],
        "kept": sum(1 for d in normalised["decisions"].values() if d["keep"]),
        "dropped": len(drops),
        "elapsed_ms": elapsed_ms,
        "applied": False,
        "note": ("offline curation evidence only; nothing is auto-applied to "
                 "the snapshot or the request path"),
        "prompt_version": "curate_pool.v2",
    }


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT)
    ap.add_argument("--tag", default="curation")
    ap.add_argument("--food-pref", action="append", default=[],
                    help="repeatable, e.g. --food-pref \"hải sản\"")
    ap.add_argument("--activity", action="append", default=[],
                    help="repeatable, filters the planner's candidate types")
    ap.add_argument("--avoid", action="append", default=[],
                    help="repeatable must_avoid terms/ids")
    ap.add_argument("--budget", type=int, default=2000000)
    ap.add_argument("--out", default="", help="default: <snapshot>/pool_curation_<tag>.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the pool/prompt, make no LLM call")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    profile = {"food_prefs": args.food_pref, "activities": args.activity,
               "must_avoid": args.avoid, "budget": args.budget,
               "start_time": "07:00", "end_time": "18:00"}
    candidates, counts = load_candidates(args.snapshot_dir, profile)
    print(f"snapshot {args.snapshot_dir}: {counts['candidates']} candidates "
          f"({counts['verified_total']} verified, "
          f"{counts['needs_verification']} need verification, "
          f"{counts['excluded']} excluded)")
    if not candidates:
        print("ERROR: no candidates for this profile", file=sys.stderr)
        return 2
    if args.dry_run:
        print(build_prompt(candidates, profile))
        return 0

    out = args.out or os.path.join(args.snapshot_dir,
                                   f"pool_curation_{args.tag}.json")
    try:
        report = curate(candidates, profile, tag=args.tag,
                        snapshot=os.path.basename(args.snapshot_dir))
    except llm_gateway.LLMError as exc:
        print(f"ERROR: LLM unavailable ({exc.reason}): {exc}", file=sys.stderr)
        return 3
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"wrote {out}: kept={report['kept']} dropped={report['dropped']} "
          f"missing={len(report['missing_ids'])} "
          f"unknown={len(report['unknown_ids'])} "
          f"({report['elapsed_ms']} ms, model={report['model']})")
    for drop in report["drops"]:
        print(f"  DROP {drop['name']} [{drop['cat']}] — {drop['reason']}")
    if report["missing_ids"]:
        print(f"  WARNING: model skipped {len(report['missing_ids'])} id(s): "
              f"{report['missing_ids'][:5]}")
    if report["unknown_ids"]:
        print(f"  WARNING: model returned {len(report['unknown_ids'])} unknown "
              f"id(s), ignored: {report['unknown_ids'][:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
