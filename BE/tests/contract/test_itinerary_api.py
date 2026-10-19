def _activity(title, position, start, end, lat=16.0611, lon=108.2274):
    return {
        "title": title,
        "position": position,
        "latitude": lat,
        "longitude": lon,
        "start_at": start,
        "end_at": end,
        "category": "visit",
        "estimated_cost_vnd": 0,
        "itinerary_version": position + 1,
    }


def test_manual_activity_mutations_increment_itinerary_once(client, trip):
    first = client.post(
        f"/v1/trips/{trip['id']}/activities",
        json=_activity("Cầu Rồng", 0, "2026-10-17T08:00:00", "2026-10-17T09:00:00"),
    )
    assert first.status_code == 201, first.text
    itinerary = first.json()
    assert itinerary["version"] == 2
    assert itinerary["activities"][0]["source"] == "manual"

    second_payload = _activity(
        "Chợ Hàn", 1, "2026-10-17T08:30:00", "2026-10-17T10:00:00"
    )
    second_payload["itinerary_version"] = 2
    second = client.post(f"/v1/trips/{trip['id']}/activities", json=second_payload)
    assert second.status_code == 201
    itinerary = second.json()
    assert itinerary["version"] == 3
    assert itinerary["warnings"][0]["activity_ids"]

    activity = itinerary["activities"][0]
    changed = client.patch(
        f"/v1/activities/{activity['id']}",
        json={
            "title": "Cầu Rồng buổi sáng",
            "version": activity["version"],
            "itinerary_version": itinerary["version"],
        },
    )
    assert changed.status_code == 200
    assert changed.json()["version"] == 4

    ids = [item["id"] for item in changed.json()["activities"]]
    reordered = client.put(
        f"/v1/trips/{trip['id']}/activities/order",
        json={"activity_ids": list(reversed(ids)), "itinerary_version": 4},
    )
    assert reordered.status_code == 200
    assert reordered.json()["version"] == 5
    assert [item["id"] for item in reordered.json()["activities"]] == list(
        reversed(ids)
    )

    stale = client.put(
        f"/v1/trips/{trip['id']}/activities/order",
        json={"activity_ids": ids, "itinerary_version": 4},
    )
    assert stale.status_code == 409
