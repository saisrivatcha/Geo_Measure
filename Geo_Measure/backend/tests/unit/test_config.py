from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import AppEnv, Settings, env_files_for

PG_URL = "postgresql+psycopg://u:p@localhost:5432/db"


def test_loads_from_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "GeoMeasure Test")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", PG_URL)
    monkeypatch.setenv("STORAGE_DIR", "/data/storage")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "10")
    monkeypatch.setenv("ALLOWED_EXTENSIONS", "kml, .ZIP")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173/, https://gis.example.com")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings(_env_file=None)

    assert settings.app_name == "GeoMeasure Test"
    assert settings.app_env is AppEnv.PRODUCTION
    assert settings.is_production
    assert settings.storage_dir == Path("/data/storage")
    assert settings.max_upload_bytes == 10 * 1024 * 1024
    assert settings.allowed_extensions == frozenset({".kml", ".zip"})
    assert settings.cors_origins == ["http://localhost:5173", "https://gis.example.com"]
    assert settings.log_level == "DEBUG"


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("MAX_UPLOAD_SIZE_MB", raising=False)
    settings = Settings(_env_file=None, database_url=PG_URL)
    assert settings.app_env is AppEnv.DEVELOPMENT
    assert settings.max_upload_size_mb == 50
    assert settings.allowed_extensions == frozenset({".kml", ".zip"})
    assert settings.cors_origins == []


def test_environment_specific_file_overrides_base_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAX_UPLOAD_SIZE_MB", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    base = tmp_path / ".env"
    base.write_text(f"DATABASE_URL={PG_URL}\nMAX_UPLOAD_SIZE_MB=50\nLOG_LEVEL=INFO\n")
    test_env = tmp_path / ".env.test"
    test_env.write_text("MAX_UPLOAD_SIZE_MB=5\n")

    settings = Settings(_env_file=(base, test_env))

    assert settings.max_upload_size_mb == 5
    assert settings.log_level == "INFO"


def test_env_files_are_layered_by_app_env() -> None:
    repo_root, backend, specific = env_files_for("test")
    assert repo_root == backend.parent.parent / ".env"
    assert backend.name == ".env"
    assert specific.name == ".env.test"


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_rejects_non_postgres_database_url() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(_env_file=None, database_url="sqlite:///geo.db")


def test_rejects_extensions_the_pipeline_cannot_process() -> None:
    with pytest.raises(ValidationError, match="Unsupported extensions"):
        Settings(_env_file=None, database_url=PG_URL, allowed_extensions="kml,kmz")


@pytest.mark.parametrize("size", ["0", "-1"])
def test_rejects_non_positive_upload_limit(size: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=PG_URL, max_upload_size_mb=size)
