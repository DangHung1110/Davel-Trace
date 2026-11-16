"""Stable-planning response contract without invoking the optimizer.

The product targets five alternatives through its own lifecycle request
(`target_count`); the planner's diverse mode keeps the stable branch's
`DIVERSE_K`, which this product contract does not set.
"""

from BE.app.modules.planning_lifecycle.domain import PlanningCommand
from BE.app.routers import itinerary


def test_stable_itinerary_public_contract_targets_five_and_hides_context():
    plan = {
        "itinerary_id": "it-1",
        "trip_id": "trip-1",
        "gate": {"passed": True, "families": {}},
        "deterministic_rank": 1,
        "deterministic_score": 0.91,
        "data_version": "danang-v1",
        "shadow": {"status": "disabled", "authoritative": False},
        "_context": {"trip": {"budget": 3_000_000}},
        "_quality": 0.91,
    }

    public = itinerary._public(plan)

    assert PlanningCommand(trip_id="t", idempotency_key="k" * 8).target_count == 5
    assert all(not key.startswith("_") for key in public)
    assert public["gate"]["passed"] is True
    assert public["shadow"]["authoritative"] is False


def test_shortage_metadata_can_report_fewer_than_target_honestly():
    response_meta = {
        "target": PlanningCommand(trip_id="t", idempotency_key="k" * 8).target_count,
        "returned": 2,
        "shortage_reason": "duplicates_removed",
    }

    assert response_meta == {
        "target": 5,
        "returned": 2,
        "shortage_reason": "duplicates_removed",
    }
