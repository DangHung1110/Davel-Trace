def test_complete_management_journey(client, profile, trip):
    activity = client.post(
        f"/v1/trips/{trip['id']}/activities",
        json={
            "poi_id": "dragon-bridge",
            "title": "Cầu Rồng",
            "position": 0,
            "latitude": 16.0611,
            "longitude": 108.2274,
            "start_at": "2026-10-17T08:00:00",
            "end_at": "2026-10-17T09:00:00",
            "category": "landmark",
            "estimated_cost_vnd": 0,
            "itinerary_version": 1,
        },
    )
    assert activity.status_code == 201

    expense = client.post(
        f"/v1/trips/{trip['id']}/expenses",
        json={"label": "Mì Quảng", "amount_vnd": 70000, "category": "food"},
    )
    assert expense.status_code == 201

    detail = client.get(f"/v1/trips/{trip['id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["profile_id"] == profile["id"]
    assert payload["itinerary"]["activities"][0]["poi_id"] == "dragon-bridge"
    assert payload["expense_summary"]["spent_vnd"] == 70000
