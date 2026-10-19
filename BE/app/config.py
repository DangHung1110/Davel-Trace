from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    snapshot_path: Path
    snapshot_name: str
    osrm_base_url: str
    route_timeout_seconds: float
    cors_origins: tuple[str, ...]


def get_settings() -> Settings:
    default_db = (REPO_ROOT / "BE" / "data" / "davel_trace.db").as_posix()
    snapshot = Path(
        os.getenv(
            "DAVEL_POI_SNAPSHOT",
            str(REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v1" / "pois.json"),
        )
    )
    origins = tuple(
        item.strip()
        for item in os.getenv(
            "DAVEL_CORS_ORIGINS",
            "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000",
        ).split(",")
        if item.strip()
    )
    return Settings(
        database_url=os.getenv("DAVEL_DATABASE_URL", f"sqlite:///{default_db}"),
        snapshot_path=snapshot,
        snapshot_name=os.getenv("DAVEL_SNAPSHOT_NAME", "danang-v1"),
        osrm_base_url=os.getenv("DAVEL_OSRM_BASE_URL", "https://router.project-osrm.org"),
        route_timeout_seconds=float(os.getenv("DAVEL_ROUTE_TIMEOUT_SECONDS", "10")),
        cors_origins=origins,
    )
