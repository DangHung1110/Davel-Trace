"""Compatibility contract for the AI planner expense context."""

from fastapi.testclient import TestClient

from BE.app import main as main_mod
from BE.app.services import agent_expenses as expenses

client = TestClient(main_mod.app, raise_server_exceptions=False)


def setup_function():
    expenses.reset()
    expenses.set_budget("t1", 3000000)


def test_post_and_summary():
    for label, amount, kind in (
        ("Mi Quang", 120000, "food"),
        ("Ve", 60000, "ticket"),
        ("Xe", 200000, "transport"),
    ):
        response = client.post(
            "/v1/expenses",
            json={"trip_id": "t1", "label": label, "amount": amount, "kind": kind},
        )
        assert response.status_code == 201, response.text
    response = client.get("/v1/expenses/summary", params={"trip_id": "t1"})
    assert response.status_code == 200
    assert response.json() == {
        "budget": 3000000,
        "spent": 380000,
        "left": 2620000,
        "alert": "",
    }


def test_bad_kind_uses_flat_agent_error_envelope():
    response = client.post(
        "/v1/expenses",
        json={"trip_id": "t1", "label": "x", "amount": 100, "kind": "shopping"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "BAD_EXPENSE"
