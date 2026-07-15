"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PRESETS_DIR = PROJECT_ROOT / "presets"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter_api_key: str = Field(..., alias="OPENROUTER_API_KEY")
    council_default_preset: str = Field("glm-stack", alias="COUNCIL_DEFAULT_PRESET")
    presets_dir: Path = Field(default=PRESETS_DIR)


@lru_cache
def get_settings() -> Settings:
    return Settings()
