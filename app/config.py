"""Application settings read from environment variables.

Every value has a default, so the service (and docker compose) starts without
an .env file. Overrides come from environment variables or an optional .env.
"""

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["debug", "info", "warning", "error", "critical"]


def _package_version() -> str:
    """Version from installed package metadata (single source: pyproject.toml)."""
    try:
        return version("devops-project")
    except PackageNotFoundError:
        return "0.0.0"


class Settings(BaseSettings):
    """Runtime configuration of the service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_version: str = Field(default_factory=_package_version)
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: LogLevel = "info"

    seed_products: int = Field(default=10, ge=1, le=100)
    seed_stock: int = Field(default=100, ge=0, le=1_000_000)

    default_page_limit: int = Field(default=20, ge=1, le=100)
    max_page_limit: int = Field(default=100, ge=1, le=1000)

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        """Accept LOG_LEVEL=INFO as well as info."""
        return value.lower() if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    """Return process-wide settings, read once."""
    return Settings()
