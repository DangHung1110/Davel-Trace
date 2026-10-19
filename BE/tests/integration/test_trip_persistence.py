from fastapi.testclient import TestClient

from BE.app import database
from BE.app.main import app
from BE.tests.integration.persistence_support import (
    configure_file_database,
    profile_payload,
    restart_client,
    trip_payload,
)


def test_trip_activity_order_and_snapshot_survive_restart(tmp_path):
    url = configure_file_database(tmp_path / "trips.db")
    try:
        with TestClient(app) as client:
            profile = client.post("/v1/profiles", json=profile_payload()).json()
            trip = client.post("/v1/trips", json=trip_payload(profile["id"])).json()
            first = client.post(
                f"/v1/trips/{trip['id']}/activities",
                json={
                    "poi_id": "dragon-bridge",
                    "title": "Cầu Rồng snapshot",
                    "latitude": 16.0611,
                    "longitude": 108.2274,
                    "start_at": "2026-10-17T08:00:00",
                    "end_at": "2026-10-17T09:00:00",
                    "category": "visit",
                    "itinerary_version": 1,
                },
            ).json()
            client.post(
                f"/v1/trips/{trip['id']}/activities",
                json={
                    "title": "Địa điểm riêng",
                    "latitude": 16.07,
                    "longitude": 108.22,
                    "start_at": "2026-10-17T10:00:00",
                    "end_at": "2026-10-17T11:00:00",
                    "category": "visit",
                    "itinerary_version": first["version"],
                },
            )

        with restart_client(url) as restarted:
            detail = restarted.get(f"/v1/trips/{trip['id']}").json()
            assert [item["title"] for item in detail["itinerary"]["activities"]] == [
                "Cầu Rồng snapshot",
                "Địa điểm riêng",
            ]
            assert detail["itinerary"]["activities"][0]["poi_id"] == "dragon-bridge"
    finally:
        database.dispose_database()
