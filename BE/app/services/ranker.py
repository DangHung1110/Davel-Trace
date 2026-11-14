"""Shadow LLM ranker (Hướng 3 + Hướng 6). NEVER on the live response path.

Given the complete plans the solver already built, this module asks an LLM
judge to order them, and writes one JSONL line to a shadow log. It never
changes what the API returns: the router only calls it from a guarded,
fire-and-forget branch behind `RANKER_SHADOW=1` (default 0 = no-op).

Protocol (from `judge_rerank_calibration.md`):
- Pairwise, both orders for every pair (10 pairs x 2 = 20 calls for 5 plans).
  A pair is a win only when both orders agree after un-swapping; otherwise it
  is a tie (0.5 win each) and lowers `swap_consistency`.
- Verdict must be `[[A]]`, `[[B]]` or `[[C]]` (tie). A spoiled answer is
  retried once, then treated as a tie; errors never reach the request path.
- Champion = max wins; ties break on the deterministic verifier key
  (feasible first, fewer violations, cheaper) then a seeded pick. The seed is
  derived from query + plan-set + rubric/model version, so the same request
  always gets the same order.
- Blind pass: plans are rendered with `POI-1..n` + checkable facts only. POI
  names, profile names and plan ids never enter the prompt; display order is
  Fisher-Yates shuffled per call.
- Reference block: the caller supplies solver verdicts per plan (feasible,
  cost, violations, POI facts) so the judge weighs trade-offs instead of
  recomputing time/cost arithmetic.
- Cache: key = hash(normalized query + plan-set + rubric/model version). A
  regenerated plan-set always misses the cache (stale rank is a bug).

The shadow line is:
{ts, query_hash, plan_ids, blind_rank, swap_consistency, latency_ms,
 model_ver, rubric_ver}
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import threading
import time

log = logging.getLogger(__name__)

RUBRIC_VER = "rubric-v1"
WEIGHTS = (("feasibility", 40), ("time/cost", 25), ("preference-fit", 20),
           ("robustness", 15))

# 3 levels up: BE/app/services/ranker.py -> BE/
SHADOW_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "ranker_shadow.jsonl")

VERDICT_RE = re.compile(r"\[\[\s*([ABC])\s*\]\]")
_CACHE: dict[str, dict] = {}
_CACHE_MAX = 256
_CACHE_LOCK = threading.Lock()
_WRITE_LOCK = threading.Lock()

SYSTEM_PROMPT = (
    "Act as an impartial judge. Compare two COMPLETE day-plans (do not "
    "re-plan, do not merge). Criteria weights: feasibility 40, time/cost 25, "
    "preference-fit 20, robustness 15. Penalize padding: extra text, filler "
    "stops or restated constraints with no new satisfied constraint score "
    "LOWER on conciseness. A longer plan is not a better plan. Do not let "
    "position, length, or any brand/POI-name influence your decision; the "
    "plans are anonymised and their order is arbitrary. The [Reference "
    "checks] block already contains the solver's checkable facts (feasibility, "
    "cost, violations): judge the trade-offs, do not recompute them. Explain "
    "briefly, then end with the verdict EXACTLY [[A]], [[B]] or [[C]] "
    "(C = tie)."
)


# --------------------------------------------------------------------------
# identity / cache keys
# --------------------------------------------------------------------------
def _canonical_query(query) -> str:
    if isinstance(query, str):
        return query.strip()
    if isinstance(query, dict):
        return json.dumps(query, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))
    return str(query or "").strip()


def query_hash(query) -> str:
    return hashlib.sha256(_canonical_query(query).encode("utf-8")).hexdigest()


def _plan_id(plan: dict, index: int) -> str:
    return str(plan.get("itinerary_id") or plan.get("plan_id")
               or plan.get("trip_id") or f"plan-{index}")


def plan_set_hash(plans: list[dict]) -> str:
    ids = []
    for index, plan in enumerate(plans):
        pid = _plan_id(plan, index)
        stops = [a.get("poi_id") for a in plan.get("activities") or []]
        ids.append([pid, stops])
    raw = json.dumps(ids, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_key(query, plans: list[dict], model_ver: str) -> str:
    raw = "|".join((query_hash(query), plan_set_hash(plans),
                    RUBRIC_VER, str(model_ver)))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# prompt rendering (blind)
# --------------------------------------------------------------------------
def _num(value) -> str:
    if value is None:
        return "?"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(f)) if f.is_integer() else f"{f:.2f}"


def _fact_map(ref: dict | None) -> dict:
    ref = ref or {}
    return {p.get("poi_id"): p for p in (ref.get("pois") or [])
            if isinstance(p, dict) and p.get("poi_id")}


def _render_plan(plan: dict, ref: dict | None = None) -> str:
    """Facts-only plan text: no names, no profile, no plan id."""
    facts = _fact_map(ref)
    lines = []
    for n, act in enumerate(plan.get("activities") or [], start=1):
        fact = facts.get(act.get("poi_id"), {})
        bits = [f"POI-{n}", f"{act.get('start', '?')}-{act.get('end', '?')}"]
        if act.get("day"):
            bits.insert(1, f"ngay {act['day']}")
        for key in ("type", "price_level", "fee", "rating"):
            if fact.get(key) is not None:
                bits.append(f"{key}={fact[key]}")
        if fact.get("intensity") is not None:
            bits.append(f"intensity={fact['intensity']}")
        lines.append(" | ".join(str(b) for b in bits))
    if not lines:
        lines.append("(no stops)")
    header = (f"stops={len(plan.get('activities') or [])} "
              f"cost={_num(plan.get('total_cost'))} "
              f"travel_min={_num(plan.get('travel_min'))} "
              f"total_min={_num(plan.get('total_min'))} "
              f"preference={_num(plan.get('preference'))}")
    return header + "\n" + "\n".join(lines)


def _reference_line(label: str, plan: dict, ref: dict | None) -> str:
    ref = ref or {}
    feasible = ref.get("feasible")
    if feasible is None:
        feasible = bool(plan.get("passed", True)) and not plan.get("violations")
    violations = list(ref.get("violations") or [])
    soft = list(ref.get("soft_violations") or plan.get("soft_violations") or [])
    cost = ref.get("cost", plan.get("total_cost"))
    return (f"{label}: feasible={'Y' if feasible else 'N'} "
            f"cost={_num(cost)} violations={len(violations)} "
            f"soft_violations={len(soft)} "
            f"travel_min={_num(ref.get('travel_min', plan.get('travel_min')))}")


def _pair_prompt(query, plan_a: dict, plan_b: dict,
                 ref_a: dict | None, ref_b: dict | None) -> str:
    user = "\n".join([
        "[Request]",
        _canonical_query(query),
        "",
        "[Plan A]",
        _render_plan(plan_a, ref_a),
        "",
        "[Plan B]",
        _render_plan(plan_b, ref_b),
        "",
        "[Reference checks]",
        _reference_line("A", plan_a, ref_a),
        _reference_line("B", plan_b, ref_b),
    ])
    return SYSTEM_PROMPT + "\n\n" + user


# --------------------------------------------------------------------------
# LLM call + parsing
# --------------------------------------------------------------------------
def _text(response) -> str:
    if isinstance(response, dict):
        return str(response.get("text") or response.get("content") or "")
    return str(response or "")


def _parse_verdict(text: str) -> str | None:
    """Last `[[A]]/[[B]]/[[C]]` in the answer; anything else = spoiled."""
    matches = VERDICT_RE.findall(text or "")
    return matches[-1] if matches else None


def _ask_letter(llm_fn, prompt: str) -> str | None:
    """One verdict letter, retried once on a spoiled/erroring answer."""
    for _ in range(2):
        try:
            response = llm_fn(prompt)
        except Exception as exc:  # noqa: BLE001 - judge failure = tie, never raise
            log.debug("ranker llm call failed: %s", exc)
            continue
        letter = _parse_verdict(_text(response))
        if letter is not None:
            return letter
    return None


# --------------------------------------------------------------------------
# verifier tie-break
# --------------------------------------------------------------------------
def _as_refs(plans: list[dict], reference) -> list[dict]:
    if reference is None:
        return [{} for _ in plans]
    if isinstance(reference, dict):
        out = []
        for index, plan in enumerate(plans):
            pid = _plan_id(plan, index)
            out.append(reference.get(index) or reference.get(pid) or {})
        return out
    refs = list(reference)
    return [refs[i] if i < len(refs) and isinstance(refs[i], dict) else {}
            for i in range(len(plans))]


def _verifier_key(plan: dict, ref: dict | None) -> tuple:
    ref = ref or {}
    feasible = ref.get("feasible")
    if feasible is None:
        feasible = bool(plan.get("passed", True)) and not plan.get("violations")
    violations = len(ref.get("violations") or [])
    violations += len(ref.get("soft_violations")
                      or plan.get("soft_violations") or [])
    cost = ref.get("cost", plan.get("total_cost"))
    try:
        cost = float(cost)
    except (TypeError, ValueError):
        cost = float("inf")
    # Sort key: feasible first, then fewer violations, then cheaper.
    return (0 if feasible else 1, violations, cost)


# --------------------------------------------------------------------------
# rank
# --------------------------------------------------------------------------
def _seed(query, plans: list[dict], model_ver: str) -> int:
    raw = "|".join((query_hash(query), plan_set_hash(plans),
                    RUBRIC_VER, str(model_ver)))
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], 16)


def _judge_pair(query, plans: list[dict], i: int, j: int,
                refs: list[dict], llm_fn, rng: random.Random) -> dict:
    display = [i, j]
    rng.shuffle(display)
    calls = []
    for first, second in ((display[0], display[1]), (display[1], display[0])):
        letter = _ask_letter(
            llm_fn, _pair_prompt(query, plans[first], plans[second],
                                 refs[first], refs[second]))
        if letter is None or letter == "C":
            winner = None
        else:
            winner = first if letter == "A" else second
        calls.append((letter, winner))

    (letter_a, winner_a), (letter_b, winner_b) = calls
    if letter_a is None or letter_b is None:
        return {"a": i, "b": j, "winner": None, "tie": True,
                "consistent": False, "reason": "spoiled"}
    if winner_a == winner_b:
        return {"a": i, "b": j, "winner": winner_a,
                "tie": winner_a is None, "consistent": True, "reason": "ok"}
    return {"a": i, "b": j, "winner": None, "tie": True,
            "consistent": False, "reason": "inconsistent"}


def rank(query, plans: list[dict], llm_fn, reference=None, *,
         model_ver: str | None = None, seed: int | None = None,
         use_cache: bool = True) -> dict:
    """Order complete plans with a swap-checked pairwise LLM judge.

    Returns {"order": [plan index...], "verdicts": [...],
             "swap_consistency": float, "model_ver": str}.
    `reference` is the caller's solver verdict per plan (list aligned by
    index, or dict keyed by index/plan id): {feasible, cost, violations,
    soft_violations, travel_min, pois:[{poi_id, type, price_level, fee,
    rating, intensity}]}.
    """
    if llm_fn is None:
        raise ValueError("rank requires an llm_fn")
    plans = list(plans or [])
    model_ver = str(model_ver or os.environ.get("JUDGE_MODEL") or "unknown")
    key = cache_key(query, plans, model_ver)
    if use_cache:
        with _CACHE_LOCK:
            cached = _CACHE.get(key)
        if cached is not None:
            return {"order": list(cached["order"]),
                    "verdicts": [dict(v) for v in cached["verdicts"]],
                    "swap_consistency": cached["swap_consistency"],
                    "model_ver": cached["model_ver"]}

    n = len(plans)
    refs = _as_refs(plans, reference)
    if seed is None:
        seed = _seed(query, plans, model_ver)
    rng = random.Random(seed)
    wins = [0.0] * n
    verdicts = []
    for i in range(n):
        for j in range(i + 1, n):
            verdict = _judge_pair(query, plans, i, j, refs, llm_fn, rng)
            verdicts.append(verdict)
            if not verdict["consistent"]:
                wins[i] += 0.5
                wins[j] += 0.5
            elif verdict["winner"] is None:
                wins[i] += 0.5
                wins[j] += 0.5
            else:
                wins[verdict["winner"]] += 1.0

    total_pairs = len(verdicts)
    consistency = (sum(1 for v in verdicts if v["consistent"]) / total_pairs
                   if total_pairs else 1.0)
    jitter = {i: rng.random() for i in range(n)}
    order = sorted(range(n), key=lambda i: (
        -wins[i], _verifier_key(plans[i], refs[i]), jitter[i]))

    result = {"order": order, "verdicts": verdicts,
              "swap_consistency": round(consistency, 4),
              "model_ver": model_ver}
    if use_cache:
        with _CACHE_LOCK:
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.clear()
            _CACHE[key] = {"order": list(order),
                           "verdicts": [dict(v) for v in verdicts],
                           "swap_consistency": result["swap_consistency"],
                           "model_ver": model_ver}
    return result


# --------------------------------------------------------------------------
# shadow log (best-effort, async-friendly)
# --------------------------------------------------------------------------
def _append(path: str, entry: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _WRITE_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def record_shadow(query, plans: list[dict], llm_fn=None, reference=None,
                  path: str | None = None, model_ver: str | None = None,
                  seed: int | None = None, use_cache: bool = True) -> dict | None:
    """Rank plans and append one shadow line. Never raises."""
    try:
        if llm_fn is None:
            llm_fn = default_llm_fn()
        started = time.perf_counter()
        result = rank(query, plans, llm_fn, reference, model_ver=model_ver,
                      seed=seed, use_cache=use_cache)
        latency_ms = int(round((time.perf_counter() - started) * 1000))
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "query_hash": query_hash(query),
            "plan_ids": [_plan_id(plan, i) for i, plan in enumerate(plans)],
            "blind_rank": result["order"],
            "swap_consistency": result["swap_consistency"],
            "latency_ms": latency_ms,
            "model_ver": result["model_ver"],
            "rubric_ver": RUBRIC_VER,
        }
        _append(path or SHADOW_PATH, entry)
        return entry
    except Exception as exc:  # noqa: BLE001 - shadow must never break a request
        log.warning("ranker shadow skipped: %s", exc)
        return None


def spawn_shadow(query, plans: list[dict], llm_fn=None, reference=None,
                 path: str | None = None, model_ver: str | None = None,
                 seed: int | None = None, use_cache: bool = True) -> threading.Thread | None:
    """Fire-and-forget `record_shadow` on a daemon thread. Never raises."""
    try:
        thread = threading.Thread(
            target=record_shadow,
            kwargs={"query": query, "plans": plans, "llm_fn": llm_fn,
                    "reference": reference, "path": path,
                    "model_ver": model_ver, "seed": seed,
                    "use_cache": use_cache},
            name="ranker-shadow", daemon=True)
        thread.start()
        return thread
    except Exception as exc:  # noqa: BLE001
        log.warning("ranker shadow thread not started: %s", exc)
        return None


# --------------------------------------------------------------------------
# default provider (only used when the caller does not inject llm_fn)
# --------------------------------------------------------------------------
def default_llm_fn(timeout_s: float = 60) -> callable:
    """Text completion through the same provider settings as the llm service.

    Kept lazy so importing this module never reads config or opens a socket.
    """
    def _call(prompt: str) -> str:
        from BE.app.config import get_settings
        from BE.app.services import fetch_json, llm

        settings = get_settings()
        url, headers, extra = llm._endpoint(settings)  # same provider switch
        user = prompt
        if user.startswith(SYSTEM_PROMPT):
            user = user[len(SYSTEM_PROMPT):].lstrip()
        body = {**extra, "messages": [{"role": "system",
                                       "content": SYSTEM_PROMPT},
                                      {"role": "user", "content": user}]}
        data = fetch_json(url, json.dumps(body).encode(), headers,
                          timeout=timeout_s)
        if "message" in data:  # Ollama
            return data["message"].get("content", "")
        choices = data.get("choices", [])  # OpenAI-compatible
        return choices[0]["message"]["content"] if choices else ""

    return _call
