from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setenv("DAVEL_DATABASE_URL", database_url)

    from BE.app import database
    from BE.app.models import Base

    database.configure_database(database_url)
    Base.metadata.create_all(database.get_engine())

    from BE.app.main import app

    with TestClient(app) as test_client:
        yield test_client

    database.dispose_database()


@pytest.fixture()
def profile_payload() -> dict:
    return {
        "display_name": "Đặng Hùng",
        "language": "vi",
        "party_type": "solo",
        "trip_purpose": "leisure",
        "spending_level": 2,
        "pace": 2,
        "fitness": 2,
        "food_preferences": ["mì Quảng"],
        "must_avoid": ["quá đông"],
    }


@pytest.fixture()
def profile(client: TestClient, profile_payload: dict) -> dict:
    response = client.post("/v1/profiles", json=profile_payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def trip_payload(profile: dict) -> dict:
    return {
        "profile_id": profile["id"],
        "title": "Cuối tuần Đà Nẵng",
        "city": "da-nang",
        "start_date": "2026-10-17",
        "end_date": "2026-10-18",
        "day_start": "07:00:00",
        "day_end": "20:00:00",
        "travelers": 2,
        "budget_vnd": 3000000,
        "transport": "motorbike",
    }


@pytest.fixture()
def trip(client: TestClient, trip_payload: dict) -> dict:
    response = client.post("/v1/trips", json=trip_payload)
    assert response.status_code == 201, response.text
    return response.json()
