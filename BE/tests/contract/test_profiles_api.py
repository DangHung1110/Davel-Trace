def test_profile_crud_and_active_selection(client, profile_payload):
    created_response = client.post("/v1/profiles", json=profile_payload)
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["version"] == 1

    listing = client.get("/v1/profiles").json()
    assert listing["active_profile_id"] == created["id"]
    assert [item["id"] for item in listing["items"]] == [created["id"]]

    updated_response = client.patch(
        f"/v1/profiles/{created['id']}",
        json={"display_name": "Hùng đi chill", "pace": 3, "version": 1},
    )
    assert updated_response.status_code == 200
    updated = updated_response.json()
    assert updated["display_name"] == "Hùng đi chill"
    assert updated["pace"] == 3
    assert updated["version"] == 2

    stale = client.patch(
        f"/v1/profiles/{created['id']}",
        json={"display_name": "Ghi đè", "version": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"

    deleted = client.delete(f"/v1/profiles/{created['id']}?version=2&confirm=true")
    assert deleted.status_code == 204
    assert client.get("/v1/profiles").json()["active_profile_id"] is None


def test_profile_with_trip_requires_delete_confirmation(client, profile, trip_payload):
    trip = client.post("/v1/trips", json=trip_payload).json()

    blocked = client.delete(f"/v1/profiles/{profile['id']}?version=1")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert blocked.json()["error"]["details"]["trips"] == 1

    deleted = client.delete(f"/v1/profiles/{profile['id']}?version=1&confirm=true")
    assert deleted.status_code == 204
    assert client.get(f"/v1/trips/{trip['id']}").status_code == 404
