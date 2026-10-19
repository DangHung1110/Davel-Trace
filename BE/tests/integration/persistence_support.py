from pathlib import Path

from fastapi.testclient import TestClient

from BE.app import database
from BE.app.main import app
from BE.app.models import Base


def configure_file_database(path: Path) -> str:
    url = f"sqlite:///{path.as_posix()}"
    database.configure_database(url)
    Base.metadata.create_all(database.get_engine())
    return url


def restart_client(url: str) -> TestClient:
    database.dispose_database()
    database.configure_database(url)
    return TestClient(app)


def profile_payload(name: str = "Đặng Hùng") -> dict:
    return {
        "display_name": name,
        "language": "vi",
        "party_type": "solo",
        "trip_purpose": "leisure",
        "spending_level": 2,
        "pace": 2,
        "fitness": 2,
        "food_preferences": ["mì Quảng"],
        "must_avoid": [],
    }


def trip_payload(profile_id: str) -> dict:
    return {
        "profile_id": profile_id,
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
