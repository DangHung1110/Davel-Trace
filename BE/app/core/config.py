"""Typed environment configuration shared by all backend capabilities."""

from __future__ import annotations

import os
from enum import Enum
from typing import Literal

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
    llm_provider: Literal["disabled", "local", "gemini", "compatible"] = "disabled"
    ollama_url: str = "http://localhost:11434"
    judge_model: str = "qwen3:14b"
    gemini_api_key: str = Field(default="", repr=False)
    llm_api_url: str = ""
    llm_api_key: str = Field(default="", repr=False)
    llm_model: str = "gemini-3.1-flash-lite"
    llm_timeout_seconds: float = Field(default=10.0, ge=1.0, le=120.0)
    llm_max_retries: int = Field(default=1, ge=0, le=2)
    llm_parse_enabled: bool = True
    llm_explanation_enabled: bool = True
    llm_shadow_enabled: bool = False
    snapshot_dir: str = os.path.join("BE", "data", "snapshots", "danang-v1")
    snapshot_name: str = ""
    google_places_key: str = Field(default="", repr=False)
    osrm_base_url: str = ""
    acceptance_db_path: str = os.path.join("BE", "data", "accepted_plans.db")
    shadow_judge_rate: float = 0.0
    identity_dev_outbox_enabled: bool = False
    identity_access_ttl_minutes: int = Field(default=15, ge=5, le=60)
    identity_refresh_ttl_days: int = Field(default=30, ge=1, le=90)
    identity_verification_ttl_hours: int = Field(default=24, ge=1, le=72)
    identity_recovery_ttl_minutes: int = Field(default=30, ge=10, le=120)

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
            if self.identity_dev_outbox_enabled:
                raise ValueError("IDENTITY_DEV_OUTBOX_ENABLED is forbidden in production")
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
