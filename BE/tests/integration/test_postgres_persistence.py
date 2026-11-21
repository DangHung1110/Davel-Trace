from __future__ import annotations

from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from BE.app.db.models import AcceptanceRecordModel
from BE.app.db.session import create_database_engine
from BE.app.modules.planning_evidence.infrastructure import (
    create_postgres_planning_evidence_service,
)


def test_acceptance_survives_three_postgres_service_reconnections(
    postgres_database_url: str,
) -> None:
    token = uuid4().hex
    key = f"restart-{token}"
    acceptance_id = None
    try:
        for index in range(3):
            engine = create_database_engine(postgres_database_url)
            try:
                service = create_postgres_planning_evidence_service(
                    sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
                )
                if index == 0:
                    saved = service.save_acceptance(
                        idempotency_key=key,
                        itinerary_id=f"it-{token}",
                        trip_id=f"trip-{token}",
                        data_version="danang-v1",
                        request={"source": "restart-test"},
                        plan={"activities": []},
                        gate={"passed": True},
                    )
                    acceptance_id = saved["acceptance_id"]
                else:
                    loaded = service.get_acceptance(acceptance_id)
                    assert loaded is not None
                    assert loaded["idempotency_key"] == key
            finally:
                engine.dispose()
    finally:
        engine = create_database_engine(postgres_database_url)
        try:
            with engine.begin() as connection:
                connection.execute(
                    delete(AcceptanceRecordModel).where(
                        AcceptanceRecordModel.idempotency_key == key
                    )
                )
        finally:
            engine.dispose()
