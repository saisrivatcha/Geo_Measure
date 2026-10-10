from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.exceptions import InvalidFileTypeError


def _envelope_keys(body: dict) -> set[str]:
    return set(body["error"])


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Not Found", "details": {}}
    }


def test_request_validation_errors_use_envelope(client: TestClient) -> None:
    response = client.get("/api/files/not-a-uuid")
    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["errors"][0]["loc"] == ["path", "file_id"]


def test_app_errors_are_translated(app: FastAPI, client: TestClient) -> None:
    @app.get("/api/_test/app-error")
    def raise_app_error() -> None:
        raise InvalidFileTypeError(details={"extension": ".exe"})

    response = client.get("/api/_test/app-error")
    assert response.status_code == 415
    assert response.json() == {
        "error": {
            "code": "INVALID_FILE_TYPE",
            "message": "Only .kml and .zip Shapefile uploads are supported.",
            "details": {"extension": ".exe"},
        }
    }


def test_unhandled_errors_hide_internals_and_log_traceback(
    app: FastAPI, client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    @app.get("/api/_test/boom")
    def boom() -> None:
        raise RuntimeError("database password is hunter2")

    with caplog.at_level(logging.ERROR, logger="app.request"):
        response = client.get("/api/_test/boom", headers={"X-Request-ID": "trace-500"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "details": {},
        }
    }
    assert "hunter2" not in response.text
    assert response.headers["x-request-id"] == "trace-500"

    record = next(r for r in caplog.records if r.getMessage() == "request.unhandled_error")
    assert record.exc_info is not None
    assert record.request_id == "trace-500"
