"""Promotion gates remain disabled until every published threshold is met."""

from BE.app.services.planning_readiness import build_readiness


class _Store:
    def __init__(self, acceptances=None, shadows=None):
        self.acceptances = acceptances or []
        self.shadows = shadows or []

    def list_acceptances(self, limit=200):
        return self.acceptances[:limit]

    def list_shadows(self, limit=5000):
        return self.shadows[:limit]


def test_zero_evidence_disables_all_learning_and_promotion():
    result = build_readiness(_Store(), canary_rate=0.4)

    assert result["pairwise_learning"]["enabled"] is False
    assert result["full_day_learning"]["enabled"] is False
    assert result["accepted_day_retrieval"]["enabled"] is False
    assert result["judge"]["promotion_ready"] is False
    assert result["judge"]["automatic_promotion"] is False
    assert result["judge"]["canary_rate"] == 0.10


def test_pairwise_and_accepted_day_thresholds_are_explicit():
    acceptances = [
        {"plan": {"activities": [{"poi_id": f"p-{index}"}]},
         "data_version": "danang-v1"}
        for index in range(50)
    ]
    shadows = [
        {"status": "completed", "shadow_top_id": "a",
         "deterministic_top_id": "a", "swap_consistent": True}
        for _ in range(150)
    ]

    result = build_readiness(
        _Store(acceptances, shadows),
        held_out_accuracy=0.72,
        mismatch=0.20,
    )

    assert result["pairwise_learning"]["enabled"] is True
    assert result["full_day_learning"]["enabled"] is True
    assert result["accepted_day_retrieval"]["enabled"] is True
    assert result["judge"]["promotion_ready"] is False
