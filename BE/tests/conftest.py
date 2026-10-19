"""Shared test fixtures (T061d). Seed snapshot + snapshot helpers.

Two snapshot dirs exist in this repo (CHECK-merge-blockers §2 "2 thư mục
danang-v1"): the LOCKED 7-POI seed at `data/snapshots/danang-v1/` (root,
used by config/quickstart S1-S7) and the big working snapshot at
`BE/data/snapshots/danang-v1/` (764 POIs, lane-A artifacts). This module
pins the LOCKED 7-POI seed for tests; do not point fixtures at the big one.

Usable two ways:
- pytest: `def test_x(seed): ...` (fixtures below).
- unittest: `from BE.tests import conftest; conftest.load_seed()`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
SEED_DIR = os.path.join(REPO_ROOT, "data", "snapshots", "danang-v1")
SEED_NAME = "danang-v1"
SEED_POI_COUNT = 7

# Canonical 1-day trip over the seed (quickstart S1/S3).
SEED_TRIP = {
    "trip_id": "s1", "user_id": "u1", "city": "da-nang",
    "start_time": "07:00", "end_time": "18:00", "days": 1,
    "travelers": 2, "budget": 3000000, "transport": ["motorbike"],
    "must_visit": [], "avoid": [], "activities": [],
    "food_prefs": [], "order_prefs": [],
}


def load_seed() -> tuple[list[dict], dict]:
    """Return (pois, cells) from the LOCKED 7-POI seed snapshot."""
    with open(os.path.join(SEED_DIR, "pois.json"), encoding="utf-8") as f:
        pois = json.load(f)["pois"]
    with open(os.path.join(SEED_DIR, "matrix.json"), encoding="utf-8") as f:
        cells = json.load(f)["cells"]
    return pois, cells


def write_snapshot(directory: str, pois: list[dict], cells: dict) -> str:
    """Write a minimal temp snapshot (pois.json + matrix.json); -> directory.

    Shared by the contract/integration fixtures so the JSON layout lives in
    one place instead of being copy-pasted in every test class.
    """
    with open(os.path.join(directory, "pois.json"), "w", encoding="utf-8") as f:
        json.dump({"pois": pois}, f, ensure_ascii=False)
    with open(os.path.join(directory, "matrix.json"), "w", encoding="utf-8") as f:
        json.dump({"ids": [p["poi_id"] for p in pois], "cells": cells}, f,
                  ensure_ascii=False)
    return directory


try:  # pytest is optional (the suite runs under unittest too)
    import pytest
except ImportError:  # pragma: no cover - clean checkout without pytest
    pytest = None

if pytest is not None:
    @pytest.fixture
    def seed():
        """(pois, cells) from the locked 7-POI seed snapshot."""
        return load_seed()

    @pytest.fixture
    def seed_trip():
        """Canonical 1-day seed trip (copy so tests can mutate it)."""
        return dict(SEED_TRIP)

    @pytest.fixture()
    def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from fastapi.testclient import TestClient

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
    def profile(client, profile_payload: dict) -> dict:
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
    def trip(client, trip_payload: dict) -> dict:
        response = client.post("/v1/trips", json=trip_payload)
        assert response.status_code == 201, response.text
        return response.json()
