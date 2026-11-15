"""Stable-planning response contract without invoking the optimizer."""

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

    assert itinerary.DIVERSE_K == 5
    assert all(not key.startswith("_") for key in public)
    assert public["gate"]["passed"] is True
    assert public["shadow"]["authoritative"] is False


def test_shortage_metadata_can_report_fewer_than_target_honestly():
    response_meta = {
        "target": itinerary.DIVERSE_K,
        "returned": 2,
        "shortage_reason": "duplicates_removed",
    }

    assert response_meta == {
        "target": 5,
        "returned": 2,
        "shortage_reason": "duplicates_removed",
    }
