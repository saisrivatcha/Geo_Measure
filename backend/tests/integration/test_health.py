from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import SettingsFactory


async def test_health_endpoint(app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(response.headers["x-request-id"]) == 32


def test_inbound_request_id_is_propagated(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "lb-trace-42"})
    assert response.headers["x-request-id"] == "lb-trace-42"


def test_malformed_inbound_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "bad id\twith spaces"})
    assert response.headers["x-request-id"] != "bad id\twith spaces"


@pytest.mark.db
def test_readiness_with_database(db_client: TestClient) -> None:
    response = db_client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_reports_unreachable_database(make_settings: SettingsFactory) -> None:
    settings = make_settings(
        database_url="postgresql+psycopg://nobody:nothing@127.0.0.1:1/missing?connect_timeout=1"
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
