"""Config loader (T004, lane C). Env + optional BE/.env file, stdlib only.

LLM_PROVIDER=local (default, Ollama demo day) | api (test env).
No secrets are committed: copy BE/.env.example -> BE/.env (gitignored).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def load_dotenv(path: str = "BE/.env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


@dataclass
class Settings:
    llm_provider: str = "local"
    ollama_url: str = "http://localhost:11434"
    judge_model: str = "qwen3:14b"
    snapshot_dir: str = os.path.join("data", "snapshots", "danang-v1")
    snapshot_name: str = "danang-v1"
    google_places_key: str = ""
    osrm_base_url: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        snap = os.environ.get("SNAPSHOT_DIR", cls.snapshot_dir)
        return cls(
            llm_provider=os.environ.get("LLM_PROVIDER", "local"),
            ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            judge_model=os.environ.get("JUDGE_MODEL", "qwen3:14b"),
            snapshot_dir=snap,
            snapshot_name=os.environ.get("SNAPSHOT_NAME",
                                         os.path.basename(snap.rstrip("/\\")) or "danang-v1"),
            google_places_key=os.environ.get("GOOGLE_PLACES_KEY", ""),
            osrm_base_url=os.environ.get("OSRM_BASE_URL", ""),
        )


def get_settings() -> Settings:
    return Settings.from_env()
