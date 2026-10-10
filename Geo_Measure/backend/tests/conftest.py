"""Shared fixtures.

Database tests run against a real PostgreSQL (``TEST_DATABASE_URL``). The schema
is built once per session by running the Alembic migrations — upgrade, full
downgrade, upgrade again — so every run also proves the migrations are
reversible. Each test then runs inside a transaction that is rolled back.
If the database is unreachable, tests marked ``db`` are skipped with a reason.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.core.config import Settings
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://geomeasure:geomeasure@localhost:5432/geomeasure_test",
)

SettingsFactory = Callable[..., Settings]


# ---- configuration & filesystem ----------------------------------------------


@pytest.fixture
def storage_dir(tmp_path: Path) -> Path:
    path = tmp_path / "storage"
    path.mkdir()
    return path


@pytest.fixture
def make_settings(storage_dir: Path) -> SettingsFactory:
    """Build isolated test settings; never reads a developer's .env files."""

    def factory(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "app_env": "test",
            "database_url": TEST_DATABASE_URL,
            "storage_dir": storage_dir,
            "log_format": "text",
            "log_level": "INFO",
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)

    return factory


@pytest.fixture
def settings(make_settings: SettingsFactory) -> Settings:
    return make_settings()


# ---- database ----------------------------------------------------------------


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = database_url
    config.attributes["skip_logging_config"] = True
    return config


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    engine = create_engine(TEST_DATABASE_URL)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL not reachable at TEST_DATABASE_URL: {exc.orig}")

    config = _alembic_config(TEST_DATABASE_URL)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after the test, even if it commits."""
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


# ---- application -------------------------------------------------------------


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_db_client(
    make_settings: SettingsFactory, db_session: Session
) -> Iterator[Callable[..., TestClient]]:
    """Build API clients (optionally with setting overrides) whose requests share
    the rolled-back test session."""
    with ExitStack() as stack:

        def factory(**overrides: Any) -> TestClient:
            application = create_app(make_settings(**overrides))
            application.dependency_overrides[get_db_session] = lambda: db_session
            return stack.enter_context(TestClient(application))

        yield factory


@pytest.fixture
def db_client(make_db_client: Callable[..., TestClient]) -> TestClient:
    return make_db_client()
