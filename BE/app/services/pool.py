"""Solution pool + MMR diverse selection (TASK-4, lane B).

The optimizer returns ONE plan per profile (argmax of the objective). For a
"show me three different days" request that is the wrong contract: three
profiles can converge on the same POI set, and a single argmax hides the
runners-up that are 1 % worse but a completely different day.

This module owns the selection half:

1. `normalize_quality`: the optimizer enumerates solutions inside a quality
   band (>= `band` * OPT). Quality is re-mapped onto [0, 1] ACROSS the band
   (floor -> 0, OPT -> 1), so the trade-off is "how much worse than the best
   is this plan" in the currency the solver optimises, not raw points.
2. `jaccard` / `jaccard_distance`: similarity of two plans = Jaccard of their
   POI sets. Identical sets -> 1.0 (redundant), disjoint sets -> 0.0.
3. `mmr_select`: greedy Maximal Marginal Relevance. The first pick is the
   best-quality plan; each next pick maximises `quality - similarity` where
   `similarity` is the MAX Jaccard against the already-selected plans. Ties
   break on quality, then on the stable pool order, so the result is
   deterministic (the endpoint must be reproducible).

Only the selection lives here: enumeration is `optimizer.optimize(
solution_pool=N)`, and the gate/validator still own feasibility, so a diverse
set can never contain an infeasible plan (every pool member satisfies the same
model constraints as the argmax).
"""

from __future__ import annotations

DEFAULT_K = 3

# Hard cross-option ceiling for the default multi-profile response: two
# returned days may share at most this share of their POI sets. Above it the
# router replaces the lower-quality plan with the next pool pick.
MAX_PAIRWISE_JACCARD = 0.6


def poi_set(plan_or_pool_item: dict) -> set[str]:
    """POI set of a pool item (`poi_ids`) or of a plan (`activities`)."""
    ids = plan_or_pool_item.get("poi_ids")
    if ids is None:
        ids = [a.get("poi_id") for a in plan_or_pool_item.get("activities") or []]
    return {pid for pid in ids if pid}


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity of two POI sets (empty vs empty -> 0.0)."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def jaccard_distance(a: set[str], b: set[str]) -> float:
    """1 - Jaccard: 0.0 = same POIs, 1.0 = nothing in common."""
    return 1.0 - jaccard(a, b)


def normalize_quality(items: list[dict], band: float = 0.95,
                      floor: float | None = None) -> list[float]:
    """Objectives -> quality in [0, 1] across the accepted band.

    `floor` is the pool's band floor (>= band * band_base). It defaults to
    ``best - (1 - band) * max(1, |best|)``. The best solution maps to 1.0 and
    the floor to 0.0, so a plan at the very edge of "acceptable" has no
    quality credit to spend on diversity. A degenerate band (best <= 0, or
    best == floor) degrades to "all equal".
    """
    if not items:
        return []
    best = max(float(it.get("objective") or 0.0) for it in items)
    if floor is None:
        floor = best - (1.0 - float(band)) * max(1.0, abs(best))
    spread = best - float(floor)
    if spread <= 0:
        return [1.0] * len(items)
    return [max(0.0, min(1.0, (float(it.get("objective") or 0.0) - float(floor))
                     / spread)) for it in items]


def mmr_select(items: list[dict], k: int = DEFAULT_K,
               band: float = 0.95, floor: float | None = None,
               qualities: list[float] | None = None) -> list[dict]:
    """Greedy MMR: top-k by (quality - max-Jaccard-to-already-selected).

    `qualities` (0..1, same order as items) wins over computing them from
    `objective`: the endpoint merges pools from DIFFERENT profiles whose
    objective scales are not comparable (savings ~0.5, balanced ~5), so the
    caller normalises per profile and passes the result in.
    Returns the selected items (copies) in pick order, each annotated with
    `mmr` = {"rank", "quality", "similarity", "score", "jaccard_to_selected"}
    so the endpoint can show WHY a plan was chosen and how different it is.
    `items` must be non-empty; a pool smaller than `k` returns the whole pool.
    """
    pool = list(items)
    if not pool:
        return []
    if qualities is not None and len(qualities) == len(pool):
        quality = [max(0.0, min(1.0, float(q))) for q in qualities]
    else:
        quality = normalize_quality(pool, band, floor)
    sets = [poi_set(it) for it in pool]
    picked: list[int] = []
    remaining = list(range(len(pool)))
    while remaining and len(picked) < max(1, int(k)):
        best_idx, best_key = None, None
        for idx in remaining:
            sim = max((jaccard(sets[idx], sets[j]) for j in picked), default=0.0)
            score = quality[idx] - sim
            # Deterministic tie-break: quality first, then pool order.
            key = (round(score, 9), round(quality[idx], 9), -idx)
            if best_key is None or key > best_key:
                best_idx, best_key = idx, key
        sim_pick = max((jaccard(sets[best_idx], sets[j]) for j in picked),
                       default=0.0)
        item = dict(pool[best_idx])
        item["mmr"] = {
            "rank": len(picked) + 1,
            "quality": round(quality[best_idx], 4),
            "similarity": round(sim_pick, 4),
            "score": round(quality[best_idx] - sim_pick, 4),
            "jaccard_to_selected": [
                round(jaccard(sets[best_idx], sets[j]), 4) for j in picked],
        }
        picked.append(best_idx)
        remaining.remove(best_idx)
        pool[best_idx] = item
    return [pool[i] for i in picked]


def pairwise_distances(items: list[dict]) -> list[dict]:
    """Pairwise (i, j, distance) Jaccard distances, for the plan report."""
    sets = [poi_set(it) for it in items]
    out = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            out.append({"i": i, "j": j,
                        "distance": round(jaccard_distance(sets[i], sets[j]), 4),
                        "similarity": round(jaccard(sets[i], sets[j]), 4)})
    return out


def pool_report(stats: dict | None, selected: list[dict],
                pool_size: int) -> dict:
    """Public `solution_pool` block: generation stats + selection evidence."""
    stats = dict(stats or {})
    return {
        "size": stats.get("in_band", pool_size),
        "found": stats.get("found", pool_size),
        "requested": stats.get("requested", pool_size),
        "band": stats.get("band"),
        "band_base_objective": stats.get("band_base_objective"),
        "best_objective": stats.get("best_objective"),
        "floor_objective": stats.get("floor_objective"),
        "best_status": stats.get("best_status"),
        "attempts": stats.get("attempts"),
        "enumeration_s": stats.get("elapsed_s"),
        "dropped_by_gate": stats.get("dropped_by_gate", 0),
        "selected": [{"rank": (it.get("mmr") or {}).get("rank"),
                      "profile": it.get("profile"),
                      "quality": (it.get("mmr") or {}).get("quality"),
                      "similarity": (it.get("mmr") or {}).get("similarity"),
                      "score": (it.get("mmr") or {}).get("score"),
                      "poi_ids": sorted(poi_set(it))}
                     for it in selected],
        "pairwise_distances": pairwise_distances(selected),
    }


def plan_quality(plan: dict) -> float:
    """Comparable 0..1 quality for 'which of these two plans loses'.

    Prefers the MMR quality (same scale across profiles), then T032's utility
    (already 0..1), then the raw objective (same-profile alternatives only).
    """
    if plan.get("_quality") is not None:
        return float(plan["_quality"])
    scores = plan.get("scores") or {}
    if scores.get("utility") is not None:
        return float(scores["utility"])
    return float(plan.get("_objective") or 0.0)


def _mmr_candidates(alternatives: list[dict]) -> list[dict]:
    """Alternatives in MMR order (quality first, then diversity).

    Called per conflicting plan with its own solution pool, so the first
    candidate is its argmax and later ones are the progressively more
    different picks. Deduplicated by POI set, empty sets ignored.
    """
    seen: set[frozenset[str]] = set()
    items: list[dict] = []
    for item in alternatives or []:
        key = frozenset(poi_set(item))
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(dict(item))
    if not items:
        return []
    if all(it.get("_objective") is not None for it in items):
        qualities = normalize_quality(
            [{"objective": it.get("_objective")} for it in items])
    else:
        qualities = [plan_quality(it) for it in items]
    return mmr_select(items, k=len(items), qualities=qualities)


def _worst_pair(plans: list[dict], ceiling: float) -> tuple[int, int, float] | None:
    worst = None
    sets = [poi_set(p) for p in plans]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            sim = jaccard(sets[i], sets[j])
            if sim > ceiling + 1e-9 and (worst is None or sim > worst[2]):
                worst = (i, j, sim)
    return worst


def enforce_pairwise(plans: list[dict], ceiling: float = MAX_PAIRWISE_JACCARD,
                     refill=None,
                     max_replacements: int | None = None
                     ) -> tuple[list[dict], dict]:
    """Guarantee pairwise POI-set Jaccard <= `ceiling` for returned options.

    For every pair above the ceiling, the LOWER-QUALITY plan is replaced with
    the next MMR pick from its own solution pool (`_pool_plans`, or lazily
    built by `refill(plan, others)`, where `others` are the plans currently
    kept beside it). Replacement candidates are taken in MMR order
    (quality first) and the first one that satisfies the ceiling against ALL
    other kept plans wins. A plan that cannot be replaced is kept as the
    best-effort least-similar option and reported (`exhausted`), so the
    endpoint never crashes and never silently drops an option.

    Returns `(plans, report)` with the report carrying the pairwise distances,
    `satisfied`, `replaced` and `exhausted` — the `solution_pool` evidence.
    """
    current = [dict(p) for p in plans]
    replaced: list[dict] = []
    exhausted: list[dict] = []
    tried: list[set[frozenset[str]]] = [
        {frozenset(poi_set(p))} for p in current]
    limit = (max_replacements if max_replacements is not None
             else max(4, 3 * max(1, len(current))))

    for _round in range(max(1, limit)):
        pair = _worst_pair(current, ceiling)
        if pair is None:
            break
        i, j, sim = pair
        qi, qj = plan_quality(current[i]), plan_quality(current[j])
        if qi < qj:
            idx = i
        elif qj < qi:
            idx = j
        else:
            idx = max(i, j)  # deterministic tie-break: replace the later one
        alternatives = list(current[idx].get("_pool_plans") or [])
        if refill is not None:
            others = [current[k] for k in range(len(current)) if k != idx]
            try:
                alternatives += list(refill(current[idx], others) or [])
            except Exception:  # noqa: BLE001 - never lose the whole response
                alternatives = alternatives
        ordered = _mmr_candidates(alternatives)

        chosen = None
        for cand in ordered:
            key = frozenset(poi_set(cand))
            if key in tried[idx]:
                continue
            tried[idx].add(key)
            worst = max((jaccard(key, poi_set(current[k]))
                         for k in range(len(current)) if k != idx),
                        default=0.0)
            if worst <= ceiling + 1e-9:
                chosen = (cand, worst)
                break
        if chosen is not None:
            cand, worst = chosen
            old_profile = current[idx].get("profile")
            cand.pop("mmr", None)  # internal ordering evidence, not plan data
            current[idx] = cand
            replaced.append({
                "profile": cand.get("profile") or old_profile,
                "replaced_profile": old_profile,
                "pair_similarity": round(sim, 4),
                "new_max_similarity": round(worst, 4),
                "poi_ids": sorted(poi_set(cand)),
            })
            continue

        # Forced-similar fallback: no candidate clears the ceiling. Take the
        # least-similar unused alternative when it improves the worst pair;
        # otherwise keep the current plan. Either way, stop and report it.
        fallback, fallback_worst = None, sim
        for cand in ordered:
            key = frozenset(poi_set(cand))
            if key in tried[idx]:
                continue
            worst = max((jaccard(key, poi_set(current[k]))
                         for k in range(len(current)) if k != idx),
                        default=0.0)
            if worst < fallback_worst:
                fallback, fallback_worst = cand, worst
        exhausted.append({
            "profile": current[idx].get("profile"),
            "pair_similarity": round(sim, 4),
            "reason": ("khong con phuong an khac trong solution pool"
                       if fallback is None else
                       "moi phuong an deu vuot nguong Jaccard"),
        })
        if fallback is not None:
            tried[idx].add(frozenset(poi_set(fallback)))
            fallback.pop("mmr", None)
            current[idx] = fallback
            replaced.append({
                "profile": fallback.get("profile"),
                "pair_similarity": round(sim, 4),
                "new_max_similarity": round(fallback_worst, 4),
                "fallback": True,
                "poi_ids": sorted(poi_set(fallback)),
            })
        break

    distances = pairwise_distances(current)
    max_sim = max((d["similarity"] for d in distances), default=0.0)
    report = {
        "max_jaccard": ceiling,
        "satisfied": max_sim <= ceiling + 1e-9,
        "max_pairwise_similarity": round(max_sim, 4),
        "pairwise_distances": distances,
        "replaced": replaced,
        "exhausted": exhausted,
    }
    return current, report
