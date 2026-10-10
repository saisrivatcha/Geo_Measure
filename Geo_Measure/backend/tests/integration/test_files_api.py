from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import File, FileStatus, FileType

pytestmark = pytest.mark.db


def _seed(session: Session, count: int) -> list[File]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    files = [
        File(
            filename=f"dataset-{i}.kml",
            file_type=FileType.KML,
            stored_path=f"{i}/original/dataset-{i}.kml",
            file_size_bytes=100 + (i * 37) % 5,
            status=FileStatus.COMPLETED if i % 2 == 0 else FileStatus.FAILED,
            created_at=base + timedelta(minutes=i),
        )
        for i in range(count)
    ]
    session.add_all(files)
    session.flush()
    return files


@pytest.mark.parametrize("path", ["/api/files", "/api/files/"])
def test_list_files_empty(db_client: TestClient, path: str) -> None:
    response = db_client.get(path)
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "page_size": 20,
        "total": 0,
        "total_pages": 0,
    }


def test_list_files_paginates_newest_first(db_client: TestClient, db_session: Session) -> None:
    _seed(db_session, 5)

    body = db_client.get("/api/files/", params={"page": 2, "page_size": 2}).json()

    assert body["total"] == 5
    assert body["total_pages"] == 3
    assert [item["filename"] for item in body["items"]] == ["dataset-2.kml", "dataset-1.kml"]
    assert "stored_path" not in body["items"][0]


def test_list_files_sorting(db_client: TestClient, db_session: Session) -> None:
    _seed(db_session, 5)
    body = db_client.get("/api/files/", params={"sort": "filename", "order": "asc"}).json()
    assert [item["filename"] for item in body["items"]] == [f"dataset-{i}.kml" for i in range(5)]

    by_size = db_client.get(
        "/api/files/", params={"sort": "file_size_bytes", "order": "desc"}
    ).json()
    sizes = [item["file_size_bytes"] for item in by_size["items"]]
    assert sizes == sorted(sizes, reverse=True)


def test_list_files_filters_by_status(db_client: TestClient, db_session: Session) -> None:
    _seed(db_session, 5)
    body = db_client.get("/api/files/", params={"status": "FAILED"}).json()
    assert body["total"] == 2
    assert {item["status"] for item in body["items"]} == {"FAILED"}


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"sort": "stored_path"},
        {"order": "sideways"},
        {"status": "DONE"},
    ],
)
def test_list_files_validates_query(db_client: TestClient, params: dict) -> None:
    response = db_client.get("/api/files/", params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("suffix", ["", "/"])
def test_get_file(db_client: TestClient, db_session: Session, suffix: str) -> None:
    (file,) = _seed(db_session, 1)
    body = db_client.get(f"/api/files/{file.id}{suffix}").json()
    assert body["id"] == str(file.id)
    assert body["file_type"] == "KML"
    assert body["source_crs_assumed"] is False


def test_get_missing_file_returns_not_found(db_client: TestClient) -> None:
    missing = uuid.uuid4()
    response = db_client.get(f"/api/files/{missing}/")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "FILE_NOT_FOUND",
            "message": "File not found.",
            "details": {"file_id": str(missing)},
        }
    }


@pytest.mark.parametrize("endpoint", ["measurements/", "geojson"])
def test_results_of_unknown_file_are_not_found(db_client: TestClient, endpoint: str) -> None:
    response = db_client.get(f"/api/files/{uuid.uuid4()}/{endpoint}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FILE_NOT_FOUND"


def test_list_files_search_and_type_filter(db_client: TestClient, db_session: Session) -> None:
    _seed(db_session, 3)
    db_session.add(
        File(
            filename="roads_100%.zip",
            file_type=FileType.SHAPEFILE,
            stored_path="x/original/roads.zip",
            file_size_bytes=1,
        )
    )
    db_session.flush()

    assert db_client.get("/api/files/", params={"q": "DATASET-1"}).json()["total"] == 1
    assert db_client.get("/api/files/", params={"q": "100%"}).json()["total"] == 1
    assert db_client.get("/api/files/", params={"q": "%"}).json()["total"] == 1  # literal %
    only_shp = db_client.get("/api/files/", params={"file_type": "SHAPEFILE"}).json()
    assert [item["filename"] for item in only_shp["items"]] == ["roads_100%.zip"]


def test_file_includes_crs_names(db_client: TestClient, db_session: Session) -> None:
    (file,) = _seed(db_session, 1)
    file.source_crs, file.measurement_crs = "EPSG:4326", "EPSG:32643"
    db_session.flush()
    body = db_client.get(f"/api/files/{file.id}/").json()
    assert body["source_crs_name"] == "WGS 84"
    assert body["measurement_crs_name"] == "WGS 84 / UTM zone 43N"


def test_meta_exposes_public_configuration(make_db_client: Callable[..., TestClient]) -> None:
    client = make_db_client(max_upload_size_mb=7)
    body = client.get("/api/meta").json()
    assert body["upload"]["max_upload_size_mb"] == 7
    assert body["upload"]["allowed_extensions"] == [".kml", ".zip"]
    assert body["measurement"]["area_unit"] == "square_meters"
    assert body["measurement"]["max_linear_distortion"] == 0.001
    assert "database_url" not in str(body).lower()
