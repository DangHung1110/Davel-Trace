from BE.app import database
from BE.app.main import app
from fastapi.testclient import TestClient

from BE.tests.integration.persistence_support import (
    configure_file_database,
    profile_payload,
    restart_client,
)


def test_profile_and_active_selection_survive_restart(tmp_path):
    url = configure_file_database(tmp_path / "profiles.db")
    try:
        with TestClient(app) as client:
            created = client.post("/v1/profiles", json=profile_payload()).json()
            updated = client.patch(
                f"/v1/profiles/{created['id']}",
                json={"display_name": "Hùng bền vững", "version": 1},
            ).json()
            assert updated["version"] == 2

        with restart_client(url) as restarted:
            listing = restarted.get("/v1/profiles").json()
            assert listing["active_profile_id"] == created["id"]
            assert listing["items"][0]["display_name"] == "Hùng bền vững"
    finally:
        database.dispose_database()
