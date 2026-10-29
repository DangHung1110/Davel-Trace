"""Auto spot-check v2 + verified-flag applier (stdlib only).

Deterministic + heuristic flags (no verdicts — human ticks those):
  D1 duplicate clusters (same norm name or <100m + name overlap)
  D2 hours empty / suspicious-24/7-indoor / unparsable format
  D3 duration outliers (p50 deviates >60% from canonical median)
  D4 rating None / perfect-5.0 (no review counts in data to confirm)
  D5 ticket True without price/source (unverified pay claim)
  D6 coords outside DN bbox
  D7 unmapped raw type (junk/removal candidates)
  D8 generic one-word names (likely dup/junk)

Usage:
  python BE/ml/data/spotcheck_v2.py --snapshot ...              # dry-run (DEFAULT)
  python BE/ml/data/spotcheck_v2.py --snapshot ... --apply-flag # write verdicts

Default mode is --dry-run: it prints the report plus would-pass / queue / fail
counts and WRITES NOTHING. --apply-flag flips `verified` to true ONLY for
unverified rows where every deterministic check in docs/verify-criteria.md is
green and no heuristic suspicion flag is raised; those rows get
`verified_by="auto-verify-v1"` and `verified_at=<today, UTC date>`.

Everything ambiguous (missing hours, single-token name, duplicate suspects,
perfect 5.0 rating, duration outlier, unverified ticket claim, unmapped type)
goes to `auto_verify_queue.jsonl` in the snapshot dir (override with
--queue-out) for a human and is NEVER flipped automatically. Rows that
deterministically violate the criteria (bad/outside bbox coords, missing name
or source, unknown cat, type/cat mismatch, duplicate poi_id, malformed hours)
are reported as `fail` and also written to the queue file if --apply-flag is
used; the file is not touched. Existing verified rows are never re-audited or
downgraded by this tool.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import date

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

from BE.ml.patm.estimate_duration import canonical_category  # noqa: E402

DN_BBOX = (15.80, 107.75, 16.35, 108.55)  # s,w,n,e
HOUR_RE = re.compile(r"^(\d{2}:\d{2})-(\d{2}:\d{2})(,|$)")
HOUR_SEG_RE = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")

AUTO_VERIFIED_BY = "auto-verify-v1"
QUEUE_FILENAME = "auto_verify_queue.jsonl"

# Canonical English categories the planner can schedule (see `poi_category`).
KNOWN_CATS = frozenset({
    "restaurant", "cafe", "attraction", "landmark", "spa", "lodging", "bar",
    "market", "beach", "nature", "museum", "park", "viewpoint", "transport",
})

# (cat, canonical type) pairs that are refinements, not contradictions: the
# curated `cat` is narrower than the coarse Google `type` label, e.g. a POI
# typed "Điểm thu hút khách du lịch" curated as `museum`. A pair outside this
# set is ambiguous (either field may be wrong) -> human queue, never a flip.
COMPATIBLE_REFINEMENTS = frozenset({
    ("museum", "attraction"),
    ("beach", "attraction"),
    ("beach", "nature"),
    ("viewpoint", "landmark"),
    ("viewpoint", "attraction"),
    ("viewpoint", "nature"),
    ("landmark", "museum"),   # war relics curated as landmark, not museum
    ("park", "attraction"),
    ("park", "nature"),
    ("nature", "attraction"),
})

# Applier decisions. `already_verified` rows are out of scope (never touched).
AUTO_PASS = "auto_pass"
QUEUE = "queue"
FAIL = "fail"
ALREADY = "already_verified"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", s).strip()


def hav(a, b, c, d) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin(math.radians(c - a) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _num(v) -> bool:
    """True for a finite real number (bools are not coordinates)."""
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(float(v)))


def _in_bbox(lat, lon) -> bool:
    s, w, n, e = DN_BBOX
    return s <= float(lat) <= n and w <= float(lon) <= e


def hours_problems(hours) -> list[str]:
    """Deterministic problems with an opening_hours list (format only).

    Overnight spans (e.g. `07:30-02:00`) and `11:00-00:00` are plausible and
    accepted; equal endpoints (`10:00-10:00`) are not. Empty/missing hours are
    NOT a format problem — they are an ambiguity handled by the caller.
    """
    problems: list[str] = []
    if isinstance(hours, str):  # defensive: accept a single string segment
        hours = [hours]
    for raw in hours or []:
        for seg in str(raw).split(","):
            seg = seg.strip()
            if not seg:
                problems.append("hours_format_invalid")
                continue
            m = HOUR_SEG_RE.match(seg)
            if not m:
                problems.append("hours_format_invalid")
                continue
            a = int(m.group(1)) * 60 + int(m.group(2))
            b = int(m.group(3)) * 60 + int(m.group(4))
            if a >= 1440 or b >= 1440:
                problems.append("hours_out_of_range")
            elif a == b:
                problems.append("hours_zero_length")
    return list(dict.fromkeys(problems))


def category_medians(pois: list[dict]) -> dict[str, float]:
    """Median visit_min.p50 per canonical type (0 when no usable sample)."""
    groups: dict[str, list[float]] = defaultdict(list)
    for p in pois:
        p50 = (p.get("visit_min") or {}).get("p50")
        groups[canonical_category(p.get("type") or "")].append(
            float(p50) if _num(p50) else 0.0)
    out: dict[str, float] = {}
    for key, vals in groups.items():
        vals = sorted(v for v in vals if v)
        out[key] = vals[len(vals) // 2] if vals else 0.0
    return out


def near_duplicate_index(pois: list[dict]) -> dict[str, list[str]]:
    """poi_id -> ids within 100m sharing >=2 name tokens (D1 near-dup rule)."""
    out: dict[str, set[str]] = defaultdict(set)
    for i, a in enumerate(pois):
        if not (_num(a.get("lat")) and _num(a.get("lon"))):
            continue
        for b in pois[i + 1:]:
            if not (_num(b.get("lat")) and _num(b.get("lon"))):
                continue
            try:
                d = hav(a["lat"], a["lon"], b["lat"], b["lon"])
            except (TypeError, ValueError):  # pragma: no cover - defensive
                continue
            if d >= 100:
                continue
            wa = set(_norm(a.get("name")).split())
            wb = set(_norm(b.get("name")).split())
            shared = wa & wb
            if shared and len(shared) >= 2:
                out[str(a["poi_id"])].add(str(b["poi_id"]))
                out[str(b["poi_id"])].add(str(a["poi_id"]))
    return {k: sorted(v) for k, v in out.items()}


class SnapshotContext:
    """Cross-row indexes used to judge one POI (built once per snapshot)."""

    def __init__(self, pois: list[dict]):
        self.id_counts = Counter(str(p.get("poi_id") or "") for p in pois)
        self.name_counts = Counter(_norm(p.get("name")) for p in pois)
        self.name_ids: dict[str, list[str]] = defaultdict(list)
        for p in pois:
            self.name_ids[_norm(p.get("name"))].append(str(p.get("poi_id") or ""))
        self.near_dups = near_duplicate_index(pois)
        self.median_p50 = category_medians(pois)


def judge_poi(poi: dict, ctx: SnapshotContext) -> dict:
    """Apply docs/verify-criteria.md to one POI.

    Returns {poi_id, name, cat, decision, hard, queue, siblings}. `hard` are
    deterministic criteria violations (-> `fail`); `queue` are undecidable or
    suspicious conditions that need a human (-> `queue`). A row auto-passes
    only when both lists are empty.
    """
    pid = str(poi.get("poi_id") or "")
    name = str(poi.get("name") or "").strip()
    cat = str(poi.get("cat") or "").strip().lower()
    typ = str(poi.get("type") or "").strip()
    hard: list[str] = []
    queue: list[str] = []
    siblings: list[str] = []

    # A1. coordinates: numeric + inside the Da Nang bbox.
    lat, lon = poi.get("lat"), poi.get("lon")
    if not (_num(lat) and _num(lon)):
        hard.append("coords_missing")
    elif not _in_bbox(lat, lon):
        hard.append("coords_outside_bbox")

    # A2. name: non-empty. Single-token names are only suspicious (D8).
    if not name:
        hard.append("name_missing")
    else:
        norm = _norm(name)
        if len(norm.split()) <= 1:
            queue.append("name_generic")
        if ctx.name_counts[norm] > 1:
            queue.append("duplicate_name")
            siblings.extend(i for i in ctx.name_ids.get(norm, []) if i != pid)

    # A3. type non-empty and consistent with `cat` (English category).
    if not typ:
        hard.append("type_missing")
    else:
        canon = canonical_category(typ)
        if canon not in KNOWN_CATS:
            # Unmapped raw label: consistency cannot be decided by script.
            queue.append("type_unmapped")
        elif cat and canon != cat and (cat, canon) not in COMPATIBLE_REFINEMENTS:
            # Coarse label vs curated cat disagree outside the known refinement
            # table: either field may be the wrong one -> human decides.
            queue.append("type_cat_mismatch")

    # A4. cat must be a category the planner knows.
    if not cat:
        hard.append("cat_missing")
    elif cat not in KNOWN_CATS:
        hard.append("cat_unknown")

    # A5. provenance: source recorded.
    if not str(poi.get("source") or "").strip():
        hard.append("source_missing")

    # A6. hours: present + plausible format (overnight spans allowed).
    hours = poi.get("opening_hours") or []
    hard.extend(hours_problems(hours))
    if not hours:
        queue.append("hours_missing")

    # A7. identity / duplicates: same poi_id is a hard data error; same name or
    # a near-duplicate cluster needs a human to decide which row to keep.
    if pid and ctx.id_counts[pid] > 1:
        hard.append("duplicate_poi_id")
    near = ctx.near_dups.get(pid) or []
    if near:
        queue.append("near_duplicate")
        siblings.extend(near)

    # Suspicion flags (same family as D3/D4/D5) that block automatic verify.
    p50 = (poi.get("visit_min") or {}).get("p50")
    med = ctx.median_p50.get(canonical_category(typ), 0.0) if typ else 0.0
    if _num(p50) and med and abs(float(p50) - med) / med > 0.6:
        queue.append("duration_outlier")
    if poi.get("rating") == 5.0:
        queue.append("rating_perfect")
    tags = poi.get("smart_tags") or {}
    if (tags.get("ticket") is True and poi.get("ticket_vnd") is None
            and "price_sources" not in poi):
        queue.append("ticket_unverified")

    hard = list(dict.fromkeys(hard))
    queue = list(dict.fromkeys(queue))
    decision = FAIL if hard else (QUEUE if queue else AUTO_PASS)
    return {
        "poi_id": pid,
        "name": name,
        "cat": cat,
        "decision": decision,
        "hard": hard,
        "queue": queue,
        "siblings": sorted(set(siblings)),
    }


def build_plan(pois: list[dict]) -> tuple[list[dict], SnapshotContext]:
    """Judge every row; already-verified rows are skipped (never re-audited)."""
    ctx = SnapshotContext(pois)
    plan: list[dict] = []
    for poi in pois:
        if poi.get("verified") is True:
            plan.append({
                "poi_id": str(poi.get("poi_id") or ""),
                "name": str(poi.get("name") or ""),
                "cat": str(poi.get("cat") or ""),
                "decision": ALREADY,
                "hard": [],
                "queue": [],
                "siblings": [],
            })
        else:
            plan.append(judge_poi(poi, ctx))
    return plan, ctx


def summarize(plan: list[dict]) -> dict:
    """Counts per decision, per category and per reason code."""
    decisions = Counter(v["decision"] for v in plan)
    by_cat: dict[str, Counter] = defaultdict(Counter)
    hard_reasons: Counter = Counter()
    queue_reasons: Counter = Counter()
    for v in plan:
        by_cat[v["cat"] or "(none)"][v["decision"]] += 1
        hard_reasons.update(v["hard"])
        queue_reasons.update(v["queue"])
    return {
        "decisions": decisions,
        "by_cat": by_cat,
        "hard_reasons": hard_reasons,
        "queue_reasons": queue_reasons,
    }


def apply_plan(pois: list[dict], plan: list[dict], *,
               verified_by: str = AUTO_VERIFIED_BY,
               today: str | None = None) -> int:
    """Flip verified=true for `auto_pass` verdicts only; return flip count.

    Pure mutation of the in-memory list (no file I/O) so tests can call it.
    """
    stamp = today or date.today().isoformat()
    by_id = {str(p.get("poi_id") or ""): p for p in pois}
    flipped = 0
    for verdict in plan:
        if verdict["decision"] != AUTO_PASS:
            continue
        poi = by_id.get(verdict["poi_id"])
        if poi is None or poi.get("verified") is True:
            continue
        poi["verified"] = True
        poi["verified_by"] = verified_by
        poi["verified_at"] = stamp
        flipped += 1
    return flipped


def queue_rows(plan: list[dict]) -> list[dict]:
    """Rows a human still has to decide (queue + fail), stable order."""
    return [v for v in plan if v["decision"] in (QUEUE, FAIL)]


def write_queue(path: str, plan: list[dict]) -> int:
    rows = queue_rows(plan)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def write_snapshot(path: str, data: dict) -> None:
    """Atomic in-place rewrite of pois.json (temp file in the same dir)."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".pois-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def compute_flags(pois: list[dict]) -> tuple[dict[str, list[str]], dict[str, float]]:
    """Legacy D1-D8 heuristic flags (report only, no verdicts)."""
    flags: dict[str, list[str]] = defaultdict(list)

    # D1 duplicates
    by_name: dict[str, list] = defaultdict(list)
    name_of = {}
    info_of = {}
    for p in pois:
        by_name[_norm(p["name"])].append(p["poi_id"])
        name_of[p["poi_id"]] = p["name"]
        src = "mới-OSM" if p["poi_id"].startswith("osm:") else "cũ-crawl"
        info_of[p["poi_id"]] = (f"{p['name']} [{p['poi_id'][:8]}] ({src}) | "
                                f"{p.get('type')} ★{p.get('rating')} "
                                f"{','.join(p.get('opening_hours') or ['no-hours'])}")
    for n, ids in by_name.items():
        if len(ids) > 1:
            flags[f"D1-dup-name:{name_of[ids[0]]}"] = [info_of[i] for i in ids]
    for i, a in enumerate(pois):
        if not (_num(a.get("lat")) and _num(a.get("lon"))):
            continue
        for b in pois[i + 1:]:
            if not (_num(b.get("lat")) and _num(b.get("lon"))):
                continue
            d = hav(a["lat"], a["lon"], b["lat"], b["lon"])
            if d < 100:
                wa, wb = set(_norm(a["name"]).split()), set(_norm(b["name"]).split())
                if wa & wb and len(wa & wb) >= 2:
                    def _rich(p):
                        return (1 if p.get("rating") else 0) + (1 if p.get("opening_hours") else 0) \
                            + (1 if p.get("verified") else 0) + (1 if p.get("ticket_vnd") else 0)

                    def _info(p):
                        src = "mới-OSM" if p["poi_id"].startswith("osm:") else "cũ-crawl"
                        return (f"{p['name']} [{p['poi_id'][:8]}] ({src}) | {p.get('type')} "
                                f"★{p.get('rating')} {','.join(p.get('opening_hours') or ['no-hours'])}")

                    ra, rb = _rich(a), _rich(b)
                    hint = f"Gợi ý giữ: {a['name']}" if ra > rb else (
                        f"Gợi ý giữ: {b['name']}" if rb > ra else "Dữ liệu ngang nhau — xem tên/loại")
                    flags[f"D1-near-dup:{a['name']} / {b['name']} ({d:.0f}m). {hint}."] = [
                        _info(a), _info(b)]

    med = category_medians(pois)

    for p in pois:
        pid = f"{p['name']} [{p['poi_id'][:8]}]"
        canon = canonical_category(p.get("type", ""))
        # D2 hours
        if not p.get("opening_hours"):
            flags[f"D2-no-hours"].append(pid)
        else:
            for h in p["opening_hours"]:
                parts = [x.strip() for x in h.split(",")]
                if not all(HOUR_RE.match(x) or x == "00:00-23:59" for x in parts):
                    flags["D2-bad-format"].append(f"{pid}: {h}")
        # D3 duration outliers
        p50 = (p.get("visit_min") or {}).get("p50", 0)
        m = med.get(canon, 0)
        if m and abs(p50 - m) / m > 0.6:
            flags["D3-dur-outlier"].append(f"{pid}: p50={p50} vs {canon}-median={m}")
        # D4 rating
        if p.get("rating") is None:
            flags["D4-no-rating"].append(pid)
        elif p.get("rating") == 5.0:
            flags["D4-rating-5.0"].append(pid)
        # D5 ticket claim w/o evidence
        st = p.get("smart_tags") or {}
        if st.get("ticket") is True and p.get("ticket_vnd") is None and "price_sources" not in p:
            flags["D5-ticket-unverified"].append(pid)
        # D6 bbox
        s, w, n, e = DN_BBOX
        if not (_num(p.get("lat")) and _num(p.get("lon"))
                and s <= p["lat"] <= n and w <= p["lon"] <= e):
            flags["D6-outside-DN"].append(pid)
        # D7 unmapped type
        if canon == p.get("type") and canon not in (
                "landmark", "transport", "market", "nature", "restaurant",
                "museum", "beach", "attraction", "park", "cafe", "lodging",
                "spa", "bar"):
            flags["D7-unmapped-type"].append(f"{pid}: {p.get('type')}")
        # D8 generic names
        if len(_norm(p["name"]).split()) <= 1:
            flags["D8-generic-name"].append(pid)
    return flags, med


FLAG_ORDER = ["D1-dup-name", "D1-near-dup", "D2-no-hours", "D2-bad-format",
              "D3-dur-outlier", "D4-no-rating", "D4-rating-5.0",
              "D5-ticket-unverified", "D6-outside-DN", "D7-unmapped-type",
              "D8-generic-name"]


def print_flags(flags: dict[str, list[str]]) -> None:
    total_human = 0
    for key in FLAG_ORDER:
        items = [v for k, v in flags.items() if k == key or k.startswith(key + ":")]
        n = sum(len(v) for v in items)
        if key in ("D2-no-hours", "D4-no-rating"):
            print(f"{key}: {n} (info, batch-fillable)")
            continue
        total_human += len(items) if key.startswith("D1") else n
        print(f"{key}: clusters={len(items)} items={n}")
        for k in list(flags):
            if k == key or k.startswith(key + ":"):
                for v in flags[k][:8]:
                    print(f"    - {v}")
                if len(flags[k]) > 8:
                    print(f"    ... +{len(flags[k]) - 8}")
    print(f"TOTAL human-review items ~= {total_human}")


def print_applier(summary: dict, *, applied: bool, flipped: int,
                  queue_path: str, queue_count: int,
                  verified_by: str = AUTO_VERIFIED_BY) -> None:
    d = summary["decisions"]
    mode = ("APPLY" if applied
            else "DRY-RUN (no files written)")
    print("--- auto-verify applier ---")
    print(f"mode={mode} criteria=docs/verify-criteria.md")
    print(f"unverified={d[AUTO_PASS] + d[QUEUE] + d[FAIL]} "
          f"auto_pass={d[AUTO_PASS]} queue={d[QUEUE]} fail={d[FAIL]} "
          f"already_verified={d[ALREADY]}")
    print("by cat (auto_pass/queue/fail):")
    for cat in sorted(summary["by_cat"]):
        c = summary["by_cat"][cat]
        print(f"  {cat:<22} {c[AUTO_PASS]:>4}/{c[QUEUE]:>4}/{c[FAIL]:>4}")
    print("queue reasons: " + (", ".join(
        f"{k}={v}" for k, v in summary["queue_reasons"].most_common()) or "-"))
    print("fail reasons: " + (", ".join(
        f"{k}={v}" for k, v in summary["hard_reasons"].most_common()) or "-"))
    if applied:
        print(f"[apply] flipped={flipped} verified_by={verified_by}")
        print(f"[apply] queue -> {queue_path} ({queue_count} rows)")
    else:
        print("[dry-run] nothing written; re-run with --apply-flag to flip "
              f"{d[AUTO_PASS]} auto-pass rows")


def write_review(path: str, flags: dict[str, list[str]]) -> None:
    L = ["# Review v2 — tick để xử lý (giữ nguyên thứ tự dòng)",
         "",
         "D1: tick 1 ô mỗi cụm: GIỮ HẾT (khác nhau thật) | GỘP (ghi tên giữ lại) | LOẠI (ghi poi_id bỏ).",
         "D3/D4/D5/D7/D8: tick Dung (đúng, giữ) hoặc Sai + ghi chú sửa.",
         ""]
    for key in FLAG_ORDER:
        ks = [k for k in flags if k == key or k.startswith(key + ":")]
        if not ks or key in ("D2-no-hours", "D4-no-rating"):
            continue
        L.append(f"## {key}")
        for k in ks:
            L.append(f"### {k}")
            for v in flags[k]:
                L.append(f"- [ ] {v} => ")
        L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Spot-check snapshot + optional auto-verify applier.")
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--review-out", default="",
                    help="write a REVIEW_V2-style tick file here")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply-flag", dest="apply", action="store_true",
                      help="flip verified=true for auto-pass rows only")
    mode.add_argument("--dry-run", dest="apply", action="store_false",
                      help="report only, write nothing (default)")
    ap.set_defaults(apply=False)
    ap.add_argument("--queue-out", default="",
                    help=f"human queue JSONL (default: <snapshot>/{QUEUE_FILENAME})")
    ap.add_argument("--verified-by", default=AUTO_VERIFIED_BY,
                    help="provenance stamp for auto-applied rows")
    args = ap.parse_args(argv)

    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    pois = data["pois"]

    flags, _ = compute_flags(pois)
    print_flags(flags)

    plan, _ = build_plan(pois)
    summary = summarize(plan)

    queue_path = args.queue_out or os.path.join(args.snapshot, QUEUE_FILENAME)
    flipped = 0
    queue_count = len(queue_rows(plan))
    if args.apply:
        flipped = apply_plan(pois, plan, verified_by=args.verified_by)
        if flipped:
            write_snapshot(path, data)
        queue_count = write_queue(queue_path, plan)
    print_applier(summary, applied=args.apply, flipped=flipped,
                  queue_path=queue_path, queue_count=queue_count,
                  verified_by=args.verified_by)

    if args.review_out:
        write_review(args.review_out, flags)
        print(f"review -> {args.review_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
