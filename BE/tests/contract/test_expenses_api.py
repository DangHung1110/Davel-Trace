def test_expense_crud_returns_current_summary(client, trip):
    created = client.post(
        f"/v1/trips/{trip['id']}/expenses",
        json={
            "label": "Khách sạn",
            "amount_vnd": 2500000,
            "category": "other",
            "spent_at": "2026-10-17T09:00:00",
        },
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["summary"]["remaining_vnd"] == 500000
    assert payload["summary"]["alert"] == "80"

    expense = payload["expense"]
    updated = client.patch(
        f"/v1/expenses/{expense['id']}",
        json={"amount_vnd": 3100000, "category": "transport", "version": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["summary"]["remaining_vnd"] == -100000
    assert updated.json()["summary"]["alert"] == "100"

    stale = client.patch(
        f"/v1/expenses/{expense['id']}", json={"amount_vnd": 1, "version": 1}
    )
    assert stale.status_code == 409

    deleted = client.delete(f"/v1/expenses/{expense['id']}?version=2")
    assert deleted.status_code == 200
    assert deleted.json()["spent_vnd"] == 0


def test_expense_validation_and_compatibility_summary(client, trip):
    invalid = client.post(
        f"/v1/trips/{trip['id']}/expenses",
        json={"label": "Sai", "amount_vnd": -1, "category": "food"},
    )
    assert invalid.status_code == 422

    summary = client.get(f"/v1/expenses/summary?trip_id={trip['id']}")
    assert summary.status_code == 200
    assert summary.json()["budget_vnd"] == 3000000
