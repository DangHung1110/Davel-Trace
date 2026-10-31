"""Typed environment configuration shared by all backend capabilities."""

from __future__ import annotations

import os
from enum import Enum

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppMode(str, Enum):
    demo = "demo"
    production = "production"
    test = "test"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_mode: AppMode = AppMode.demo
    database_url: str = Field(default="", repr=False)
    allowed_origins: str = "http://127.0.0.1:5501,http://localhost:5501"
    llm_provider: str = "local"
    ollama_url: str = "http://localhost:11434"
    judge_model: str = "qwen3:14b"
    snapshot_dir: str = os.path.join("data", "snapshots", "danang-v1")
    snapshot_name: str = ""
    google_places_key: str = Field(default="", repr=False)
    osrm_base_url: str = ""
    acceptance_db_path: str = os.path.join("BE", "data", "accepted_plans.db")
    shadow_judge_rate: float = 0.0

    @field_validator("shadow_judge_rate", mode="before")
    @classmethod
    def validate_shadow_rate(cls, value: object) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        return parsed if 0.0 <= parsed <= 0.10 else 0.0

    @field_validator("allowed_origins")
    @classmethod
    def normalize_origins(cls, value: str) -> str:
        return ",".join(part.strip() for part in value.split(",") if part.strip())

    @model_validator(mode="after")
    def validate_production_contract(self) -> "Settings":
        if not self.snapshot_name:
            self.snapshot_name = (
                os.path.basename(self.snapshot_dir.rstrip("/\\")) or "danang-v1"
            )
        if self.app_mode is AppMode.production:
            if not self.database_url:
                raise ValueError("DATABASE_URL is required in production mode")
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError(
                    "DATABASE_URL must use postgresql+psycopg in production mode"
                )
            if not self.cors_origins or "*" in self.cors_origins:
                raise ValueError("ALLOWED_ORIGINS must list explicit production origins")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [part for part in self.allowed_origins.split(",") if part]

    @property
    def database_required(self) -> bool:
        return self.app_mode is AppMode.production

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(_env_file="BE/.env")


def get_settings() -> Settings:
    return Settings.from_env()
