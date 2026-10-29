import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from BE.app import main as main_mod
from BE.app.config import Settings
from BE.app.routers import planning_evidence, select


client = TestClient(main_mod.app, raise_server_exceptions=False)


def _plan():
    trip = {
        "trip_id": "trip-accept",
        "start_time": "07:00",
        "end_time": "18:00",
        "budget": 500_000,
        "must_visit": [],
        "avoid": [],
    }
    pois = [{
        "poi_id": "museum",
        "verified": True,
        "type": "museum",
        "fee": 20_000,
        "opening_hours": ["07:00-17:00"],
    }]
    return {
        "itinerary_id": "it-accept",
        "trip_id": "trip-accept",
        "activities": [{"poi_id": "museum", "start": "08:00", "end": "09:00"}],
        "deterministic_rank": 1,
        "deterministic_score": 0.91,
        "data_version": "danang-test",
        "_context": {"trip": trip, "pois": pois, "travel": {}},
    }


def test_idempotent_selection_and_readiness_api():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        settings = Settings(
            snapshot_name="danang-test",
            acceptance_db_path=str(Path(tmp) / "accepted.db"),
        )
        old_select = select.get_settings
        old_evidence = planning_evidence.get_settings
        select.get_settings = lambda: settings
        planning_evidence.get_settings = lambda: settings
        select.reset_store()
        select.register([_plan()])
        try:
            payload = {
                "itinerary_id": "it-accept",
                "idempotency_key": "mobile-choice-accept-001",
            }
            first = client.post("/v1/itinerary/select", json=payload)
            second = client.post("/v1/itinerary/select", json=payload)
            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text
            acceptance_id = first.json()["acceptance"]["acceptance_id"]
            assert second.json()["acceptance"]["acceptance_id"] == acceptance_id

            record = client.get(f"/v1/acceptances/{acceptance_id}")
            assert record.status_code == 200, record.text
            assert record.json()["plan"]["itinerary_id"] == "it-accept"

            listing = client.get("/v1/acceptances?trip_id=trip-accept")
            assert listing.status_code == 200
            assert listing.json()["count"] == 1

            readiness = client.get("/v1/planning/readiness")
            assert readiness.status_code == 200
            assert readiness.json()["accepted_complete_days"] == 1
            assert readiness.json()["accepted_day_retrieval"]["enabled"] is False
        finally:
            select.get_settings = old_select
            planning_evidence.get_settings = old_evidence
            select.reset_store()


def test_legacy_select_persists_but_keeps_exact_response_shape():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        settings = Settings(
            snapshot_name="danang-test",
            acceptance_db_path=str(Path(tmp) / "accepted.db"),
        )
        old_select = select.get_settings
        old_evidence = planning_evidence.get_settings
        select.get_settings = lambda: settings
        planning_evidence.get_settings = lambda: settings
        select.reset_store()
        select.register([_plan()])
        try:
            response = client.post(
                "/v1/itinerary/select", json={"itinerary_id": "it-accept"}
            )
            assert response.status_code == 200, response.text
            assert response.json() == {"active_id": "it-accept"}
            listing = client.get("/v1/acceptances?trip_id=trip-accept")
            assert listing.json()["count"] == 1
        finally:
            select.get_settings = old_select
            planning_evidence.get_settings = old_evidence
            select.reset_store()
