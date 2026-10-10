"""Strongly typed application settings.

Values are resolved in this order (highest priority first):

1. real environment variables (how Docker Compose injects configuration);
2. ``backend/.env.<APP_ENV>`` - environment-specific overrides, e.g. ``.env.test``;
3. ``backend/.env``;
4. the repository-root ``.env`` shared with Docker Compose.

Missing files are ignored.
"""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Extensions the processing pipeline can actually handle. ALLOWED_EXTENSIONS may
# narrow this set via configuration but can never widen it.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".kml", ".zip"})

BYTES_PER_MB = 1024 * 1024
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application configuration. Field names map case-insensitively to env vars."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "GeoMeasure"
    app_env: AppEnv = AppEnv.DEVELOPMENT

    database_url: str = Field(
        ...,
        description="SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host:5432/db",
    )
    database_echo: bool = False

    storage_dir: Path = Field(default=Path("storage"))

    max_upload_size_mb: int = Field(default=50, gt=0, le=2048)
    max_extracted_size_mb: int = Field(
        default=500,
        gt=0,
        description="Upper bound on the total uncompressed size of a Shapefile ZIP.",
    )
    allowed_extensions: Annotated[frozenset[str], NoDecode] = SUPPORTED_EXTENSIONS
    geojson_preview_max_features: int = Field(
        default=5000,
        gt=0,
        le=100_000,
        description="Upper bound on features returned by the map-preview GeoJSON endpoint.",
    )

    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    @field_validator("database_url")
    @classmethod
    def _require_postgres(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+")):
            raise ValueError("DATABASE_URL must be a PostgreSQL SQLAlchemy URL")
        return value

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def _parse_extensions(cls, value: object) -> frozenset[str]:
        items = _split_csv(value)
        normalized = frozenset(
            item.lower() if item.startswith(".") else f".{item.lower()}" for item in items
        )
        if not normalized:
            raise ValueError("ALLOWED_EXTENSIONS must contain at least one extension")
        unsupported = normalized - SUPPORTED_EXTENSIONS
        if unsupported:
            raise ValueError(
                f"Unsupported extensions {sorted(unsupported)}; "
                f"supported: {sorted(SUPPORTED_EXTENSIONS)}"
            )
        return normalized

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> list[str]:
        return [origin.rstrip("/") for origin in _split_csv(value)]

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * BYTES_PER_MB

    @property
    def max_extracted_bytes(self) -> int:
        return self.max_extracted_size_mb * BYTES_PER_MB

    @property
    def max_request_body_bytes(self) -> int:
        """Upload limit plus headroom for multipart boundaries and headers."""
        return self.max_upload_bytes + MULTIPART_OVERHEAD_BYTES

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION


def _split_csv(value: object) -> list[str]:
    """Accept either a comma separated string or an iterable of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, (list, tuple, set, frozenset)):
        parts = [str(item) for item in value]
    else:
        raise ValueError("Expected a comma separated string or a list of strings")
    return [part.strip() for part in parts if part.strip()]


def env_files_for(app_env: str) -> tuple[Path, ...]:
    """Env files to load, lowest priority first."""
    return (
        BACKEND_DIR.parent / ".env",
        BACKEND_DIR / ".env",
        BACKEND_DIR / f".env.{app_env}",
    )


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings, resolved once. Tests construct ``Settings`` directly."""
    app_env = os.getenv("APP_ENV", AppEnv.DEVELOPMENT.value)
    return Settings(_env_file=env_files_for(app_env))
