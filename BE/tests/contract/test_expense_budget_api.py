from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from BE.app.core.config import get_settings
from BE.app.db.models import AccountModel, RoleAssignmentModel, TripLifecycleEventModel
from BE.app.db.session import session_scope
from BE.app.main import app
from BE.app.modules.identity.security import hash_password
from BE.app.modules.identity.service import IdentityService, now_utc


def _account(email, password):
    settings = get_settings()
    with session_scope(settings.database_url) as session:
        account = AccountModel(
            email_normalized=email, password_hash=hash_password(password),
            status="active", consented_at=now_utc(), verified_at=now_utc(),
        )
        session.add(account)
        session.flush()
        account_id = account.account_id
        session.add(RoleAssignmentModel(account_id=account_id, role="traveler"))
    token = IdentityService(settings).login(email, password, "expense contract", "test", "contract-008")
    return account_id, {"Authorization": f"Bearer {token['access_token']}"}


def test_expense_crud_summary_idempotency_export_and_isolation() -> None:
    settings = get_settings()
    password = "TravelDemo123"
    owner_id, headers = _account(f"expense-{uuid4().hex}@example.com", password)
    other_id, other_headers = _account(f"expense-other-{uuid4().hex}@example.com", password)
    client = TestClient(app)
    try:
        profile = client.put("/v1/profile", headers=headers, json={"display_name": "Hùng"})
        assert profile.status_code == 200, profile.text
        trip = client.post("/v1/trips", headers={
            **headers, "Idempotency-Key": f"trip-{uuid4().hex}"
        }, json={
            "title": "Ba ngày Đà Nẵng", "start_date": "2026-11-10",
            "end_date": "2026-11-12", "traveler_count": 2,
            "indicative_budget": 1000000, "day_start": "07:00:00",
            "day_end": "21:00:00",
        }).json()

        body = {
            "label": "Khách sạn", "amount_vnd": 800000,
            "category": "accommodation", "spent_at": "2026-11-10T12:00:00+07:00",
            "notes": "Hai đêm",
        }
        create_headers = {**headers, "Idempotency-Key": f"expense-{uuid4().hex}"}
        first = client.post(f"/v1/trips/{trip['id']}/expenses", headers=create_headers, json=body)
        repeated = client.post(f"/v1/trips/{trip['id']}/expenses", headers=create_headers, json=body)
        assert first.status_code == repeated.status_code == 201, first.text
        assert first.json()["expense"]["id"] == repeated.json()["expense"]["id"]
        assert first.json()["summary"]["alert"] == "80"

        denied = client.get(f"/v1/trips/{trip['id']}/expenses", headers=other_headers)
        assert denied.status_code == 404

        expense = first.json()["expense"]
        updated = client.patch(f"/v1/expenses/{expense['id']}", headers=headers, json={
            "version": expense["version"], "amount_vnd": 1000000,
            "label": expense["label"], "category": expense["category"],
            "spent_at": expense["spent_at"], "notes": expense["notes"],
        })
        assert updated.status_code == 200, updated.text
        assert updated.json()["summary"]["alert"] == "100"
        stale = client.patch(f"/v1/expenses/{expense['id']}", headers=headers, json={
            "version": expense["version"], "amount_vnd": 900000,
        })
        assert stale.status_code == 409

        revised_trip = client.patch(f"/v1/trips/{trip['id']}", headers=headers, json={
            "expected_version": trip["version"], "indicative_budget": 1200000,
        })
        assert revised_trip.status_code == 200, revised_trip.text
        budget = client.get(f"/v1/trips/{trip['id']}/budget", headers=headers)
        assert budget.status_code == 200
        assert budget.json()["budget_vnd"] == 1200000
        assert len(budget.json()["revisions"]) == 1
        summary = client.get(f"/v1/trips/{trip['id']}/expenses/summary", headers=headers)
        assert summary.json()["alert"] == "80"

        exported = client.get(f"/v1/trips/{trip['id']}/expenses/export", headers=headers)
        assert exported.status_code == 200
        assert exported.json()["summary"]["spent_vnd"] == 1000000
        account_export = client.post("/v1/account/exports", headers=headers, json={
            "current_password": password, "confirmation": "XUẤT DỮ LIỆU",
        })
        exported_trip = account_export.json()["payload"]["product_data"]["trips"][0]
        assert exported_trip["expenses"][0]["amount_vnd"] == 1000000
        assert exported_trip["budget_revisions"][0]["new_amount_vnd"] == 1200000
        assert [event["event_type"] for event in exported_trip["expense_audit"]] == ["created", "updated"]

        deleted = client.delete(
            f"/v1/expenses/{expense['id']}", headers=headers,
            params={"version": updated.json()["expense"]["version"]},
        )
        assert deleted.status_code == 200
        assert deleted.json()["spent_vnd"] == 0
    finally:
        with session_scope(settings.database_url) as session:
            session.execute(delete(TripLifecycleEventModel).where(
                TripLifecycleEventModel.account_id.in_((owner_id, other_id))
            ))
            for account_id in (owner_id, other_id):
                account = session.scalar(select(AccountModel).where(AccountModel.account_id == account_id))
                if account:
                    session.delete(account)
