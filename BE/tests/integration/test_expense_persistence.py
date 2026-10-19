from fastapi.testclient import TestClient

from BE.app import database
from BE.app.main import app
from BE.tests.integration.persistence_support import (
    configure_file_database,
    profile_payload,
    restart_client,
    trip_payload,
)


def test_expenses_survive_restart_and_cascade_with_trip(tmp_path):
    url = configure_file_database(tmp_path / "expenses.db")
    try:
        with TestClient(app) as client:
            profile = client.post("/v1/profiles", json=profile_payload()).json()
            trip = client.post("/v1/trips", json=trip_payload(profile["id"])).json()
            client.post(
                f"/v1/trips/{trip['id']}/expenses",
                json={"label": "Mì Quảng", "amount_vnd": 70000, "category": "food"},
            )

        with restart_client(url) as restarted:
            persisted = restarted.get(f"/v1/trips/{trip['id']}/expenses").json()
            assert persisted["items"][0]["label"] == "Mì Quảng"
            assert persisted["summary"]["spent_vnd"] == 70000
            deleted = restarted.delete(
                f"/v1/trips/{trip['id']}?version=1&confirm=true"
            )
            assert deleted.status_code == 204
            assert restarted.get(f"/v1/trips/{trip['id']}").status_code == 404
    finally:
        database.dispose_database()
