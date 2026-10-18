"""Local-LLM judge runner for T028 pair batches (lane A, stdlib + REST).

Same in/out contract as gemini_judge.py but talks to an OpenAI-compatible
endpoint (LM Studio / Ollama / vLLM). No API key, no quota.

Usage (repo root, LM Studio server on :1234):
  python BE/ml/patm/local_judge.py --in C:/tmp/judge_q.jsonl --out C:/tmp/judge_local.jsonl --limit 5
  python BE/ml/patm/local_judge.py --in C:/tmp/judge_q.jsonl --out C:/tmp/judge_local.jsonl --limit 1000
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

CHOICE_RE = re.compile(r'"choice"\s*:\s*"(first|second|tie)"', re.IGNORECASE)


def judge(prompt: str, base_url: str, model: str,
          timeout: int = 120) -> str | None:
    url = base_url.rstrip("/") + "/chat/completions"
    # Qwen3 thinking eats short max_tokens -> empty content; /no_think
    # forces direct answer (judge needs 1 JSON word, no reasoning trace).
    prompt = prompt.rstrip() + "\n/no_think"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 50,
    }).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        text = data["choices"][0]["message"]["content"] or ""
        m = CHOICE_RE.search(text)
        return m.group(1).lower() if m else None
    except Exception as e:  # noqa: BLE001 - server hiccups, caller retries
        print(f"  call failed: {type(e).__name__}", flush=True)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    ap.add_argument("--model", default="qwen3-8b")
    args = ap.parse_args()

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
    print(f"todo={len(rows)} (skipped {len(done)} done) "
          f"model={args.model} @ {args.base_url}", flush=True)
    ok = fail = 0
    t0 = time.time()
    with open(args.outp, "a", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            c = judge(r["prompt"], args.base_url, args.model)
            if c is None:
                time.sleep(3)
                c = judge(r["prompt"], args.base_url, args.model)
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
                dt = time.time() - t0
                print(f"[{i + 1}/{len(rows)}] {c} ok={ok} fail={fail} "
                      f"{dt / (i + 1):.1f}s/call", flush=True)
            time.sleep(args.sleep)
    print(f"done: ok={ok} fail={fail} -> {args.outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
