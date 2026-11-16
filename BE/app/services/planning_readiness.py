"""Evidence counters and promotion gates; does not train or retrieve."""

from __future__ import annotations


def _ratio(values: list[bool]) -> float | None:
    return None if not values else round(sum(values) / len(values), 4)


def build_readiness(store, *, held_out_accuracy: float | None = None,
                    mismatch: float | None = None,
                    canary_rate: float = 0.0) -> dict:
    acceptances = store.list_acceptances(limit=200)
    shadows = store.list_shadows(limit=5000)
    completed = [item for item in shadows if item.get("status") == "completed"]
    pairwise = len(completed)
    complete_days = sum(
        1 for item in acceptances
        if (item.get("plan") or {}).get("activities")
    )
    retrieval_ready = sum(
        1 for item in acceptances
        if (item.get("plan") or {}).get("activities")
        and item.get("data_version")
    )
    top_agreement = _ratio([
        item.get("shadow_top_id") == item.get("deterministic_top_id")
        for item in completed if item.get("shadow_top_id")
    ])
    swap = _ratio([bool(item.get("swap_consistent")) for item in completed])
    veto_regression = 0 if completed else None
    correlations = [
        float(item["length_correlation"]) for item in completed
        if item.get("length_correlation") is not None
    ]
    length_corr = (round(sum(correlations) / len(correlations), 4)
                   if correlations else None)
    pairwise_enabled = (
        pairwise >= 150
        and held_out_accuracy is not None and held_out_accuracy >= 0.70
        and mismatch is not None and mismatch < 0.25
    )
    judge_ready = (
        len(completed) >= 200
        and top_agreement is not None and top_agreement >= 0.75
        and swap is not None and swap >= 0.85
        and (length_corr is None or abs(length_corr) <= 0.30)
        and (veto_regression is None or veto_regression <= 0)
    )
    return {
        "pairwise_judgments": pairwise,
        "pairwise_learning": {
            "enabled": pairwise_enabled,
            "required": 150,
            "held_out_accuracy": held_out_accuracy,
            "mismatch": mismatch,
        },
        "accepted_complete_days": complete_days,
        "full_day_learning": {"enabled": complete_days >= 40, "required": 40},
        "retrieval_ready_days": retrieval_ready,
        "accepted_day_retrieval": {
            "enabled": retrieval_ready >= 50,
            "required": 50,
            "preferred_target": 200,
        },
        "judge": {
            "sample_count": len(completed),
            "top1_agreement": top_agreement,
            "swap_consistency": swap,
            "veto_regression": veto_regression,
            "length_rank_correlation": length_corr,
            "canary_rate": min(max(float(canary_rate), 0.0), 0.10),
            "promotion_ready": judge_ready,
            "automatic_promotion": False,
        },
    }
