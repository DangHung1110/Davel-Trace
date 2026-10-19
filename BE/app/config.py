"""Unified settings for the travel-agent and management APIs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: str | Path = REPO_ROOT / "BE" / ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "local"
    ollama_url: str = "http://localhost:11434"
    judge_model: str = "qwen3:14b"
    snapshot_dir: str = str(REPO_ROOT / "data" / "snapshots" / "danang-v1")
    snapshot_name: str = "danang-v1"
    google_places_key: str = ""
    osrm_base_url: str = "https://router.project-osrm.org"
    database_url: str = (
        f"sqlite:///{(REPO_ROOT / 'BE' / 'data' / 'davel_trace.db').as_posix()}"
    )
    snapshot_path: Path = (
        REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v1" / "pois.json"
    )
    route_timeout_seconds: float = 10.0
    cors_origins: tuple[str, ...] = (
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    )


def get_settings() -> Settings:
    load_dotenv()
    agent_snapshot = os.getenv(
        "SNAPSHOT_DIR", str(REPO_ROOT / "data" / "snapshots" / "danang-v1")
    )
    management_snapshot = Path(
        os.getenv(
            "DAVEL_POI_SNAPSHOT",
            str(REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v1" / "pois.json"),
        )
    )
    default_db = (REPO_ROOT / "BE" / "data" / "davel_trace.db").as_posix()
    origins = tuple(
        item.strip()
        for item in os.getenv(
            "DAVEL_CORS_ORIGINS",
            "http://127.0.0.1:5500,http://localhost:5500,"
            "http://127.0.0.1:3000,http://localhost:3000",
        ).split(",")
        if item.strip()
    )
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "local"),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        judge_model=os.getenv("JUDGE_MODEL", "qwen3:14b"),
        snapshot_dir=agent_snapshot,
        snapshot_name=os.getenv(
            "SNAPSHOT_NAME", Path(agent_snapshot.rstrip("/\\")).name or "danang-v1"
        ),
        google_places_key=os.getenv("GOOGLE_PLACES_KEY", ""),
        osrm_base_url=os.getenv(
            "DAVEL_OSRM_BASE_URL",
            os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org"),
        ),
        database_url=os.getenv("DAVEL_DATABASE_URL", f"sqlite:///{default_db}"),
        snapshot_path=management_snapshot,
        route_timeout_seconds=float(os.getenv("DAVEL_ROUTE_TIMEOUT_SECONDS", "10")),
        cors_origins=origins,
    )
