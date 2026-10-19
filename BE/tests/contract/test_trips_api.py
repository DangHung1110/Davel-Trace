def test_trip_crud_and_version_conflict(client, profile, trip_payload):
    created_response = client.post("/v1/trips", json=trip_payload)
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["city"] == "da-nang"
    assert created["version"] == 1

    listing = client.get(f"/v1/trips?profile_id={profile['id']}").json()
    assert [item["id"] for item in listing["items"]] == [created["id"]]

    updated = client.patch(
        f"/v1/trips/{created['id']}",
        json={"title": "Đà Nẵng tự túc", "budget_vnd": 3500000, "version": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    stale = client.patch(
        f"/v1/trips/{created['id']}",
        json={"title": "Ghi đè", "version": 1},
    )
    assert stale.status_code == 409

    blocked = client.delete(f"/v1/trips/{created['id']}?version=2")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "CONFIRMATION_REQUIRED"

    deleted = client.delete(f"/v1/trips/{created['id']}?version=2&confirm=true")
    assert deleted.status_code == 204


def test_trip_rejects_non_danang_and_more_than_two_days(client, profile, trip_payload):
    wrong_city = {**trip_payload, "city": "ha-noi"}
    assert client.post("/v1/trips", json=wrong_city).status_code == 422

    too_long = {**trip_payload, "end_date": "2026-10-20"}
    response = client.post("/v1/trips", json=too_long)
    assert response.status_code == 422
