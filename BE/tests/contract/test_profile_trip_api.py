from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from BE.app.core.config import get_settings
from BE.app.db.models import AccountModel, RoleAssignmentModel, TripLifecycleEventModel
from BE.app.db.session import session_scope
from BE.app.main import app
from BE.app.modules.identity.security import hash_password
from BE.app.modules.identity.service import IdentityService, now_utc


def test_profile_trip_activity_and_lifecycle_round_trip() -> None:
    settings = get_settings()
    email = f"management-{uuid4().hex}@example.com"
    password = "TravelDemo123"
    with session_scope(settings.database_url) as session:
        account = AccountModel(
            email_normalized=email,
            password_hash=hash_password(password),
            status="active",
            consented_at=now_utc(),
            verified_at=now_utc(),
        )
        session.add(account)
        session.flush()
        account_id = account.account_id
        session.add(RoleAssignmentModel(account_id=account_id, role="traveler"))

    try:
        credentials = IdentityService(settings).login(
            email, password, "management contract", "test", "contract-007"
        )
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        client = TestClient(app)

        profile = client.put("/v1/profile", headers=headers, json={
            "display_name": "Hùng",
            "party_type": "friends",
            "trip_purpose": "discovery",
            "pace": 2,
            "fitness": 2,
            "spending_level": 2,
            "allergies": ["đậu phộng"],
        })
        assert profile.status_code == 200, profile.text
        assert profile.json()["profile"]["allergies"] == ["đậu phộng"]

        trip_body = {
            "title": "Ba ngày Đà Nẵng",
            "start_date": "2026-11-10",
            "end_date": "2026-11-12",
            "traveler_count": 2,
            "indicative_budget": 3000000,
            "preferred_transport": "motorbike",
            "day_start": "07:00:00",
            "day_end": "21:00:00",
        }
        create_headers = {**headers, "Idempotency-Key": f"trip-{uuid4().hex}"}
        created = client.post("/v1/trips", headers=create_headers, json=trip_body)
        repeated = client.post("/v1/trips", headers=create_headers, json=trip_body)
        assert created.status_code == repeated.status_code == 201
        trip = created.json()
        assert repeated.json()["id"] == trip["id"]
        assert len(trip["days"]) == 3

        activated = client.put("/v1/trips/active", headers=headers, json={
            "trip_id": trip["id"], "expected_selection_version": 0,
        })
        assert activated.status_code == 200

        day = trip["days"][0]
        activity_headers = {
            **headers,
            "Idempotency-Key": f"activity-{uuid4().hex}",
        }
        activity = client.post(
            f"/v1/trips/{trip['id']}/days/{day['id']}/activities",
            headers=activity_headers,
            json={
                "title": "Cầu Rồng",
                "kind": "visit",
                "start_time": "19:00:00",
                "end_time": "20:00:00",
            },
        )
        assert activity.status_code == 201, activity.text
        updated_activity = client.patch(
            f"/v1/activities/{activity.json()['id']}",
            headers=headers,
            json={
                "expected_version": activity.json()["version"],
                "progress_state": "completed",
            },
        )
        assert updated_activity.json()["status"] == "completed"

        archived = client.post(
            f"/v1/trips/{trip['id']}/archive",
            headers=headers,
            json={"expected_version": trip["version"]},
        )
        assert archived.status_code == 200
        listing = client.get("/v1/trips", headers=headers).json()
        assert listing["active_trip_id"] is None
        assert listing["items"] == []

        restored = client.post(
            f"/v1/trips/{trip['id']}/restore",
            headers=headers,
            json={"expected_version": archived.json()["version"]},
        )
        assert restored.status_code == 200
        assert len(restored.json()["days"]) == 3

        exported = client.post("/v1/account/exports", headers=headers, json={
            "current_password": password,
            "confirmation": "XUẤT DỮ LIỆU",
        })
        assert exported.status_code == 201
        assert exported.json()["payload"]["product_data"]["trips"][0]["id"] == trip["id"]
    finally:
        with session_scope(settings.database_url) as session:
            session.execute(delete(TripLifecycleEventModel).where(
                TripLifecycleEventModel.account_id == account_id
            ))
            account = session.scalar(select(AccountModel).where(
                AccountModel.account_id == account_id
            ))
            if account:
                session.delete(account)
