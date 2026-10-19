"""Gemini judge runner for T028 pair batches (lane A, stdlib + REST only).

Reads prompts emitted by make_pairs --emit-judge-batch, calls Gemini
generateContent, writes one JSON per line {first_id, second_id, choice}
for make_pairs.collect_judge. Swap-check happens downstream (both orders
are in the batch; inconsistent mirrors are dropped at collect time).

Key: BE/.env GEMINI_KEY (never printed, never committed).
Pacing: free tier ~15 RPM; per-call latency (~15-20s) self-paces.
Resume: skips (first_id, second_id) already in --out.

Usage (repo root, Windows: native C:/ paths for python):
  python BE/ml/patm/gemini_judge.py --in C:/tmp/judge_q.jsonl --out C:/tmp/judge_gemini.jsonl --limit 100
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

DEFAULT_MODEL = "gemini-3.8-flash"
CHOICE_RE = re.compile(r'"choice"\s*:\s*"(first|second|tie)"')


def load_key() -> str:
    env = os.path.join(_REPO_ROOT, "BE", ".env")
    with open(env, encoding="utf-8") as f:
        for line in f:
            if line.startswith("GEMINI_KEY="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("GEMINI_KEY missing in BE/.env")


def judge(prompt: str, key: str, model: str, timeout: int = 90) -> str | None:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        m = CHOICE_RE.search(text)
        return m.group(1) if m else None
    except Exception as e:  # noqa: BLE001 - network flakiness, caller retries
        print(f"  call failed: {type(e).__name__}", flush=True)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    key = load_key()
    done: set[str] = set()
    if os.path.exists(args.outp):
        with open(args.outp, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done.add(r["first_id"] + ">" + r["second_id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    rows = []
    with open(args.inp, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["first_id"] + ">" + r["second_id"] not in done:
                rows.append(r)
    rows = rows[:args.limit]
    print(f"todo={len(rows)} (skipped {len(done)} done) model={args.model}",
          flush=True)
    ok = fail = 0
    with open(args.outp, "a", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            c = judge(r["prompt"], key, args.model)
            if c is None:  # one retry
                time.sleep(5)
                c = judge(r["prompt"], key, args.model)
            if c is None:
                fail += 1
                print(f"[{i + 1}/{len(rows)}] FAIL {r['first_id'][:8]}",
                      flush=True)
            else:
                ok += 1
                f.write(json.dumps({"first_id": r["first_id"],
                                    "second_id": r["second_id"],
                                    "choice": c}, ensure_ascii=False) + "\n")
                f.flush()
                print(f"[{i + 1}/{len(rows)}] {c} ok={ok} fail={fail}",
                      flush=True)
            time.sleep(args.sleep)
    print(f"done: ok={ok} fail={fail} -> {args.outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
