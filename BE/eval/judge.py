"""LLM-judge Profit/BE (T050, lane A). Swap-checked pairwise preference.

Live run happens LATER on full pairs (T003b snapshot + T028 batch);
this module + its mock tests are the shippable unit now.

Protocol (research R3/R8 pattern):
- Ollama-compatible client: base URL via `OLLAMA_URL`
  (default http://localhost:11434), model via `JUDGE_MODEL`
  (default qwen3:14b), temp 0.1, <=2 retries, JSON-only answers.
- Swap-check: every pair is asked TWICE (A/B orders swapped); the
  verdict counts only if both answers agree after un-swapping AND both
  parse as valid JSON {"winner": "A"|"B"|"tie"}. Anything else is
  discarded with a reason (inconsistent | bad_json | transport).
- Cost log: {ts, model, prompt/completion tokens, est_usd} appended as
  JSONL (`COST_LOG` path or given file). Local Ollama = $0; api models
  use a per-1k price table overridable via `JUDGE_PRICE_PER_1K_USD`.

Stdlib only (urllib). The `client` callable is injectable so unit tests
monkeypatch it — no network in tests, no live LLM billed.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "qwen3:14b")
COST_LOG = os.environ.get("JUDGE_COST_LOG", "BE/eval/judge_cost.jsonl")
MAX_RETRIES = 2

VALID_WINNERS = ("A", "B", "tie")


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def ollama_client(prompt: str, model: str = JUDGE_MODEL,
                  url: str = OLLAMA_URL,
                  temperature: float = 0.1) -> dict:
    """POST /api/chat non-streaming. Returns {text, prompt_tokens,
    completion_tokens}. Raises RuntimeError after MAX_RETRIES failures."""
    body = json.dumps({"model": model, "temperature": temperature,
                       "stream": False,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    last_err = "unknown"
    for _ in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url.rstrip("/") + "/api/chat", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            text = data.get("message", {}).get("content", "")
            return {"text": text,
                    "prompt_tokens": int(data.get("prompt_eval_count")
                                         or _estimate_tokens(prompt)),
                    "completion_tokens": int(data.get("eval_count")
                                             or _estimate_tokens(text))}
        except Exception as e:  # noqa: BLE001 - retry then wrap
            last_err = str(e)
    raise RuntimeError(f"ollama judge failed: {last_err}")


def judge_prompt(first: dict, second: dict) -> str:
    fa = f"{first['name']} ({first.get('type')}, rating {first.get('rating')}, " \
         f"tags {first.get('tags')})"
    fb = f"{second['name']} ({second.get('type')}, rating {second.get('rating')}, " \
         f"tags {second.get('tags')})"
    return ("Chon thu tu tot hon cho khach thich van dong truoc, thu gian sau. "
            "Chi tra JSON {\"winner\": \"A\"|\"B\"|\"tie\"}, khong giai thich.\n"
            f"A: {fa}\nB: {fb}")


def _parse_winner(text: str) -> str | None:
    try:
        winner = json.loads(text.strip().splitlines()[-1])["winner"]
    except (ValueError, KeyError, IndexError, AttributeError):
        return None
    return winner if winner in VALID_WINNERS else None


class CostLog:
    """Append-only JSONL cost ledger (tokens + est USD)."""

    def __init__(self, path: str = COST_LOG, model: str = JUDGE_MODEL,
                 price_per_1k_usd: float = 0.0):
        self.path = path
        self.model = model
        self.price = price_per_1k_usd
        self.totals = {"prompt_tokens": 0, "completion_tokens": 0}

    def add(self, prompt_tokens: int, completion_tokens: int) -> dict:
        self.totals["prompt_tokens"] += prompt_tokens
        self.totals["completion_tokens"] += completion_tokens
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": self.model,
                 "prompt_tokens": prompt_tokens,
                 "completion_tokens": completion_tokens,
                 "est_usd": round((prompt_tokens + completion_tokens) / 1000
                                  * self.price, 6)}
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry


def judge_pair(a: dict, b: dict, client=ollama_client,
               cost: CostLog | None = None) -> dict:
    """Swap-checked verdict for ordered pair (a, b).

    Returns {"verdict": +1 (a first) | -1 | 0 (tie) | None (discarded),
             "reason": "ok" | "inconsistent" | "bad_json" | "transport", ...}.
    """
    try:
        r1 = client(judge_prompt(a, b))
        r2 = client(judge_prompt(b, a))
    except Exception as e:  # noqa: BLE001 - transport failure
        return {"verdict": None, "reason": "transport", "detail": str(e)[:200]}
    if cost is not None:
        cost.add(r1.get("prompt_tokens", 0) + r2.get("prompt_tokens", 0),
                 r1.get("completion_tokens", 0) + r2.get("completion_tokens", 0))
    w1, w2 = _parse_winner(r1.get("text", "")), _parse_winner(r2.get("text", ""))
    if w1 is None or w2 is None:
        return {"verdict": None, "reason": "bad_json"}
    # un-swap: r2 answered about (b, a), map back to (a, b) frame
    unswap = {"A": "B", "B": "A", "tie": "tie"}
    if unswap[w2] != w1:
        return {"verdict": None, "reason": "inconsistent",
                "detail": f"{w1} vs swapped {w2}"}
    return {"verdict": {"A": 1, "B": -1, "tie": 0}[w1], "reason": "ok"}


def judge_batch(pairs: list[dict], pois: dict, client=ollama_client,
                cost: CostLog | None = None) -> list[dict]:
    """Judge stored pairs; attach {judge_verdict, judge_reason} (T028 600)."""
    out = []
    for p in pairs:
        r = judge_pair(pois[p["first_id"]], pois[p["second_id"]], client, cost)
        out.append({**p, "judge_verdict": r["verdict"], "judge_reason": r["reason"]})
    kept = sum(1 for o in out if o["judge_verdict"] is not None)
    print(f"judged {len(out)} pairs, kept {kept} "
          f"({sum(1 for o in out if o['judge_reason'] == 'inconsistent')} inconsistent, "
          f"{sum(1 for o in out if o['judge_reason'] == 'bad_json')} bad_json)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T050 LLM judge (live run later)")
    ap.add_argument("--pairs", default="")
    ap.add_argument("--snapshot", default=os.path.join("data", "snapshots", "danang-v1"))
    ap.add_argument("--out", default="")
    ap.add_argument("--cost-log", default=COST_LOG)
    args = ap.parse_args(argv)
    if not args.pairs:
        print("no --pairs given: live run pending full T003b pairs (see docstring).")
        return 2
    with open(os.path.join(args.snapshot, "pois.json"), encoding="utf-8") as f:
        pois = {p["poi_id"]: p for p in json.load(f)["pois"]}
    with open(args.pairs, encoding="utf-8") as f:
        pairs = json.load(f)
    cost = CostLog(args.cost_log)
    out = judge_batch(pairs, pois, cost=cost)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"wrote -> {args.out}; totals {cost.totals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
