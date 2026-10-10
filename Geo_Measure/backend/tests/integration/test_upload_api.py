"""End-to-end upload processing through the HTTP API against PostgreSQL."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from pyproj import Geod
from shapely.geometry import LineString, Point, Polygon
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FeatureMeasurement, File, FileStatus
from app.repositories.feature_measurement_repository import FeatureMeasurementRepository
from app.repositories.file_repository import FileRepository
from tests.factories import (
    kml_document,
    kml_line,
    kml_multigeometry,
    kml_placemark,
    kml_point,
    kml_polygon,
    square,
    write_shapefile_zip,
    write_symlink_zip,
    write_zip,
)

pytestmark = pytest.mark.db

PARCEL_RING = [(78.48, 17.38), (78.49, 17.38), (78.49, 17.39), (78.48, 17.39), (78.48, 17.38)]
ROAD = [(78.48, 17.38), (78.50, 17.40)]


def upload(client: TestClient, filename: str, content: bytes, path: str = "/api/files/") -> Any:
    return client.post(path, files={"file": (filename, content, "application/octet-stream")})


def survey_kml() -> bytes:
    return kml_document(
        (
            "Parcels",
            [
                kml_placemark(
                    "Parcel 1", kml_polygon(PARCEL_RING), placemark_id="p1", data={"owner": "Ravi"}
                ),
                kml_placemark("Well", kml_point(78.485, 17.385)),
            ],
        ),
        (
            "Roads",
            [
                kml_placemark("Road", kml_line(ROAD), placemark_id="r1"),
                kml_placemark("Mixed", kml_multigeometry(kml_point(78.48, 17.38), kml_line(ROAD))),
            ],
        ),
    )


def shapefile_zip(tmp_path: Path, frame: gpd.GeoDataFrame, **kwargs: Any) -> bytes:
    return write_shapefile_zip(tmp_path, frame, **kwargs).read_bytes()


def feature_rows(session: Session, file_id: str) -> int:
    return session.scalar(
        select(func.count())
        .select_from(FeatureMeasurement)
        .where(FeatureMeasurement.file_id == uuid.UUID(file_id))
    )


# ---- success -----------------------------------------------------------------------


def test_upload_kml(db_client: TestClient, storage_dir: Path) -> None:
    response = upload(db_client, "survey.kml", survey_kml())

    assert response.status_code == 201, response.text
    body = response.json()
    file = body["file"]
    assert file["status"] == "COMPLETED"
    assert file["file_type"] == "KML"
    assert file["feature_count"] == 4
    assert file["source_crs"] == "EPSG:4326"
    assert file["measurement_crs"] == "EPSG:32644"
    assert file["completed_at"] is not None
    assert file["processing_error"] is None
    assert response.headers["location"] == f"/api/files/{file['id']}/"
    assert body["links"]["measurements"] == f"/api/files/{file['id']}/measurements/"

    summary = body["summary"]
    assert summary["total_features"] == 4
    assert summary["measured_features"] == 2
    assert summary["not_required_features"] == 1
    assert summary["unsupported_features"] == 1
    assert (summary["polygon_count"], summary["line_count"], summary["point_count"]) == (1, 1, 1)
    assert summary["other_count"] == 1

    # Original kept, normalised GeoJSON written, extraction directory empty.
    root = storage_dir / file["id"]
    assert (root / "original" / "survey.kml").exists()
    assert (root / "processed" / "features.geojson").exists()
    assert list((root / "extracted").iterdir()) == []


def test_geographic_upload_is_measured_in_square_meters_not_degrees(db_client: TestClient) -> None:
    """The API-level version of the critical CRS guarantee."""
    body = upload(db_client, "parcel.kml", survey_kml()).json()
    file_id = body["file"]["id"]

    feature = db_client.get(f"/api/files/{file_id}/measurements/").json()["features"][0]

    assert feature["source_crs"] == "EPSG:4326"
    assert feature["measurement_crs"] != feature["source_crs"]
    assert feature["measurement"]["unit"] == "square_meters"
    expected, _ = Geod(ellps="WGS84").geometry_area_perimeter(Polygon(PARCEL_RING))
    assert feature["measurement"]["value"] == pytest.approx(abs(expected), rel=1e-3)
    assert feature["measurement"]["value"] > 1_000_000  # ~1.18 km², not 1e-4 "degrees²"


def test_upload_projected_shapefile_with_known_area(db_client: TestClient, tmp_path: Path) -> None:
    frame = gpd.GeoDataFrame(
        {"name": ["plot"], "zone": [7]},
        geometry=[square(500_000, 1_900_000, 100)],  # exactly 10 000 m²
        crs="EPSG:32643",
    )
    response = upload(db_client, "plots.zip", shapefile_zip(tmp_path, frame))
    assert response.status_code == 201, response.text
    file = response.json()["file"]
    assert file["file_type"] == "SHAPEFILE"
    assert (file["source_crs"], file["measurement_crs"]) == ("EPSG:32643", "EPSG:32643")

    feature = db_client.get(f"/api/files/{file['id']}/measurements/").json()["features"][0]
    assert feature["measurement"]["value"] == pytest.approx(10_000.0)
    assert feature["measurement"]["area_hectares"] == pytest.approx(1.0)
    assert feature["measurement"]["display"] == "1.00 ha"
    assert feature["source_feature_id"] == "0"
    assert feature["properties"] == {"name": "plot", "zone": 7}


def test_shapefile_without_prj_completes_with_crs_unavailable(
    db_client: TestClient, tmp_path: Path
) -> None:
    frame = gpd.GeoDataFrame(
        geometry=[square(500_000, 1_900_000, 100), square(500_200, 1_900_000, 50)],
        crs="EPSG:32643",
    )
    body = upload(db_client, "noprj.zip", shapefile_zip(tmp_path, frame, with_prj=False)).json()
    file = body["file"]

    assert file["status"] == "COMPLETED"
    assert file["source_crs"] is None
    assert file["measurement_crs"] is None
    assert body["summary"]["crs_unavailable_features"] == 2
    assert body["summary"]["measured_features"] == 0
    assert body["summary"]["polygon_count"] == 2
    assert body["summary"]["measured_polygon_count"] == 0

    features = db_client.get(f"/api/files/{file['id']}/measurements/").json()["features"]
    assert features[0]["measurement_status"] == "CRS_UNAVAILABLE"
    assert features[0]["measurement"] is None
    assert "no coordinate reference system" in features[0]["measurement_error"]

    geojson = db_client.get(f"/api/files/{file['id']}/geojson").json()
    assert all(feature["geometry"] is None for feature in geojson["features"])
    assert geojson["metadata"]["features_without_geometry"] == 2


def test_invalid_geometry_is_repaired_or_flagged_without_failing_the_file(
    db_client: TestClient, tmp_path: Path
) -> None:
    bowtie = Polygon(
        [(500_000, 1_900_000), (500_100, 1_900_100), (500_100, 1_900_000), (500_000, 1_900_100)]
    )
    frame = gpd.GeoDataFrame(geometry=[bowtie, square(501_000, 1_900_000, 10)], crs="EPSG:32643")
    body = upload(db_client, "bowtie.zip", shapefile_zip(tmp_path, frame)).json()
    assert body["file"]["status"] == "COMPLETED"

    repaired = db_client.get(f"/api/files/{body['file']['id']}/measurements/").json()["features"][0]
    assert repaired["geometry_valid"] is False
    assert repaired["geometry_repaired"] is True
    assert repaired["measurement"]["value"] == pytest.approx(5_000.0)


# ---- measurements & geojson endpoints --------------------------------------------------------


def test_measurements_pagination(db_client: TestClient, tmp_path: Path) -> None:
    frame = gpd.GeoDataFrame(
        {"n": list(range(7))},
        geometry=[square(500_000 + i * 200, 1_900_000, 10 + i) for i in range(7)],
        crs="EPSG:32643",
    )
    file_id = upload(db_client, "many.zip", shapefile_zip(tmp_path, frame)).json()["file"]["id"]

    body = db_client.get(
        f"/api/files/{file_id}/measurements", params={"page": 2, "page_size": 3}
    ).json()

    assert (body["page"], body["page_size"], body["total"], body["total_pages"]) == (2, 3, 7, 3)
    assert [f["feature_index"] for f in body["features"]] == [3, 4, 5]
    assert body["summary"]["total_features"] == 7  # summary always covers the whole file
    assert body["summary"]["total_area_square_meters"] == pytest.approx(
        sum((10 + i) ** 2 for i in range(7))
    )

    last = db_client.get(f"/api/files/{file_id}/measurements/", params={"page": 3, "page_size": 3})
    assert [f["feature_index"] for f in last.json()["features"]] == [6]


@pytest.mark.parametrize("params", [{"page_size": 0}, {"page_size": 501}, {"page": 0}])
def test_measurements_validate_page_size(db_client: TestClient, params: dict) -> None:
    file_id = upload(db_client, "s.kml", survey_kml()).json()["file"]["id"]
    response = db_client.get(f"/api/files/{file_id}/measurements/", params=params)
    assert response.status_code == 422


def test_geojson_reprojects_to_wgs84_for_display(db_client: TestClient, tmp_path: Path) -> None:
    frame = gpd.GeoDataFrame(
        {"name": ["road"]},
        geometry=[LineString([(500_000, 1_900_000), (500_500, 1_900_500)])],
        crs="EPSG:32644",
    )
    file_id = upload(db_client, "road.zip", shapefile_zip(tmp_path, frame)).json()["file"]["id"]

    body = db_client.get(f"/api/files/{file_id}/geojson").json()

    assert body["type"] == "FeatureCollection"
    feature = body["features"][0]
    lon, lat = feature["geometry"]["coordinates"][0]
    assert lon == pytest.approx(81.0, abs=1e-6)  # central meridian of UTM 44N
    assert 17.0 < lat < 17.3
    assert feature["properties"] == {"name": "road"}
    assert feature["geomeasure"]["measurement_type"] == "LENGTH"
    assert body["metadata"]["display_crs"] == "EPSG:4326"
    assert body["metadata"]["source_crs"] == "EPSG:32644"  # stored CRS unchanged

    # The stored (source CRS) geometry is untouched.
    measurements = db_client.get(f"/api/files/{file_id}/measurements/").json()
    assert measurements["source_crs"] == "EPSG:32644"


def test_geojson_preview_is_capped(make_db_client: Any, tmp_path: Path) -> None:
    client = make_db_client(geojson_preview_max_features=2)
    frame = gpd.GeoDataFrame(
        geometry=[Point(500_000 + i, 1_900_000) for i in range(5)], crs="EPSG:32643"
    )
    file_id = upload(client, "pts.zip", shapefile_zip(tmp_path, frame)).json()["file"]["id"]

    metadata = client.get(f"/api/files/{file_id}/geojson").json()["metadata"]
    assert metadata["total_features"] == 5
    assert metadata["returned_features"] == 2
    assert metadata["truncated"] is True

    limited = client.get(f"/api/files/{file_id}/geojson", params={"limit": 1}).json()
    assert limited["metadata"]["returned_features"] == 1
    assert [f["id"] for f in limited["features"]] == [0]


# ---- rejected uploads (no record) -------------------------------------------------------------


def _file_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(File))


@pytest.mark.parametrize(
    ("filename", "content", "status_code", "code"),
    [
        ("notes.txt", b"hello", 415, "INVALID_FILE_TYPE"),
        ("tour.kmz", b"PK\x03\x04", 415, "INVALID_FILE_TYPE"),
        ("empty.kml", b"", 400, "EMPTY_FILE"),
    ],
)
def test_rejected_before_processing(
    db_client: TestClient,
    db_session: Session,
    filename: str,
    content: bytes,
    status_code: int,
    code: str,
) -> None:
    response = upload(db_client, filename, content)
    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
    assert _file_count(db_session) == 0


def test_upload_over_limit(make_db_client: Any, db_session: Session) -> None:
    client = make_db_client(max_upload_size_mb=1)
    response = upload(client, "big.kml", b"<kml>" + b" " * (1024 * 1024) + b"</kml>")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert _file_count(db_session) == 0


def test_request_body_far_over_limit_is_refused_before_parsing(make_db_client: Any) -> None:
    client = make_db_client(max_upload_size_mb=1)
    response = upload(client, "huge.kml", b"x" * (3 * 1024 * 1024))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_chunked_body_over_limit_is_refused_while_streaming(make_db_client: Any) -> None:
    client = make_db_client(max_upload_size_mb=1)
    boundary = "geomeasure-test"

    def body() -> Any:  # a generator body is sent with Transfer-Encoding: chunked
        disposition = 'Content-Disposition: form-data; name="file"; filename="big.kml"'
        yield f"--{boundary}\r\n{disposition}\r\n\r\n".encode()
        for _ in range(40):
            yield b"x" * 65_536
        yield f"\r\n--{boundary}--\r\n".encode()

    response = client.post(
        "/api/files/",
        content=body(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert response.json()["error"]["details"]["max_bytes"] == 2 * 1024 * 1024


def test_missing_file_field(db_client: TestClient) -> None:
    response = db_client.post("/api/files/", data={"other": "x"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ---- failed processing (record kept as FAILED) --------------------------------------------------


def _assert_failed(client: TestClient, response: Any, status_code: int, code: str) -> dict:
    assert response.status_code == status_code, response.text
    error = response.json()["error"]
    assert error["code"] == code
    file = client.get(f"/api/files/{error['details']['file_id']}/").json()
    assert file["status"] == "FAILED"
    assert file["processing_error"] == error["message"]
    assert file["completed_at"] is not None
    return file


def test_corrupted_zip_fails_processing(db_client: TestClient) -> None:
    response = upload(db_client, "broken.zip", b"PK\x03\x04 definitely not a zip")
    file = _assert_failed(db_client, response, 400, "INVALID_ARCHIVE")

    results = db_client.get(f"/api/files/{file['id']}/measurements/")
    assert results.status_code == 409
    assert results.json()["error"]["code"] == "FILE_NOT_PROCESSED"
    assert results.json()["error"]["details"]["status"] == "FAILED"


@pytest.mark.parametrize("omitted", [".dbf", ".shx"])
def test_missing_shapefile_component_fails_processing(
    db_client: TestClient, tmp_path: Path, omitted: str
) -> None:
    frame = gpd.GeoDataFrame(geometry=[square(0, 0, 1)], crs="EPSG:32643")
    response = upload(db_client, "parts.zip", shapefile_zip(tmp_path, frame, omit=(omitted,)))
    file = _assert_failed(db_client, response, 400, "MISSING_SHAPEFILE_COMPONENTS")
    assert omitted in file["processing_error"]


@pytest.mark.parametrize(
    "archive_builder",
    [
        lambda tmp: write_zip(
            tmp / "evil.zip", {"../../etc/evil.shp": b"x", "a.shx": b"x", "a.dbf": b"x"}
        ),
        lambda tmp: write_symlink_zip(tmp / "link.zip", "a.shp", "/etc/passwd"),
    ],
    ids=["path-traversal", "symlink"],
)
def test_malicious_archive_fails_processing(
    db_client: TestClient, tmp_path: Path, storage_dir: Path, archive_builder: Any
) -> None:
    response = upload(db_client, "evil.zip", archive_builder(tmp_path).read_bytes())
    file = _assert_failed(db_client, response, 400, "UNSAFE_ARCHIVE")
    assert list((storage_dir / file["id"] / "extracted").iterdir()) == []
    assert not (tmp_path.parent / "etc").exists()


def test_malformed_kml_fails_processing(db_client: TestClient) -> None:
    response = upload(db_client, "bad.kml", b"<kml><Document><Placemark>")
    _assert_failed(db_client, response, 400, "INVALID_KML")


def test_kml_without_features_fails_processing(db_client: TestClient) -> None:
    response = upload(db_client, "empty.kml", kml_document())
    _assert_failed(db_client, response, 422, "EMPTY_DATASET")


# ---- transaction safety ----------------------------------------------------------------------


def test_failure_while_persisting_features_leaves_no_partial_rows(
    db_client: TestClient,
    db_session: Session,
    tmp_path: Path,
    storage_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Feature 80 of 100 fails: rows 0-79 must not survive and the file must be FAILED."""
    original_insert = FeatureMeasurementRepository.bulk_insert

    def insert_80_then_fail(self: FeatureMeasurementRepository, rows: Any, **kwargs: Any) -> int:
        # Persist rows 0-79 in small batches (as large uploads do), then fail.
        original_insert(self, list(rows)[:80], batch_size=25)
        self.session.flush()
        raise RuntimeError("simulated failure at feature 80")

    monkeypatch.setattr(FeatureMeasurementRepository, "bulk_insert", insert_80_then_fail)
    frame = gpd.GeoDataFrame(
        geometry=[square(500_000 + i * 20, 1_900_000, 10) for i in range(100)], crs="EPSG:32643"
    )

    response = upload(db_client, "hundred.zip", shapefile_zip(tmp_path, frame))

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert "simulated" not in response.text  # internal detail not leaked
    file_id = error["details"]["file_id"]

    db_session.expire_all()
    file = db_session.get(File, uuid.UUID(file_id))
    assert file.status is FileStatus.FAILED
    assert file.feature_count is None
    assert feature_rows(db_session, file_id) == 0
    assert not (storage_dir / file_id / "processed" / "features.geojson").exists()
    assert (storage_dir / file_id / "original" / "hundred.zip").exists()


def test_trailing_slash_variants_are_equivalent(db_client: TestClient) -> None:
    created = upload(db_client, "s.kml", survey_kml(), path="/api/files")
    assert created.status_code == 201
    file_id = created.json()["file"]["id"]
    assert db_client.get(f"/api/files/{file_id}/measurements").status_code == 200
    assert db_client.get(f"/api/files/{file_id}/geojson/").status_code == 200


def test_collection_feature_reported_not_supported(db_client: TestClient) -> None:
    file_id = upload(db_client, "s.kml", survey_kml()).json()["file"]["id"]
    features = db_client.get(f"/api/files/{file_id}/measurements/").json()["features"]
    mixed = next(f for f in features if f["geometry_type"] == "GeometryCollection")
    assert mixed["measurement_status"] == "NOT_SUPPORTED"
    assert mixed["measurement"] is None


# ---- feature detail & workspace stats ----------------------------------------------------------


def test_feature_detail_includes_geometry(db_client: TestClient) -> None:
    file_id = upload(db_client, "s.kml", survey_kml()).json()["file"]["id"]

    body = db_client.get(f"/api/files/{file_id}/features/0").json()

    assert body["feature_index"] == 0
    assert body["geometry_type"] == "Polygon"
    assert body["display_geometry"]["type"] == "Polygon"
    assert body["geometry"]["coordinates"][0][0][:2] == [78.48, 17.38]
    assert body["measurement"]["type"] == "AREA"

    missing = db_client.get(f"/api/files/{file_id}/features/99")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "FEATURE_NOT_FOUND"


def test_workspace_stats_aggregate_across_files(db_client: TestClient, tmp_path: Path) -> None:
    empty = db_client.get("/api/stats").json()
    assert empty["files"]["total"] == 0
    assert empty["features"]["total_features"] == 0

    upload(db_client, "s.kml", survey_kml())
    frame = gpd.GeoDataFrame(geometry=[square(500_000, 1_900_000, 10)], crs="EPSG:32643")
    upload(db_client, "p.zip", shapefile_zip(tmp_path, frame))
    upload(db_client, "bad.zip", b"PK\x03\x04 nope")

    stats = db_client.get("/api/stats").json()
    assert stats["files"] == {"total": 3, "completed": 2, "in_progress": 0, "failed": 1}
    assert stats["features"]["total_features"] == 5
    assert stats["features"]["measured_features"] == 3
    assert stats["features"]["polygon_count"] == 2
    assert stats["features"]["measured_polygon_count"] == 2
    assert stats["features"]["measured_line_count"] == 1
    assert stats["features"]["unsupported_features"] == 1


def test_storage_is_discarded_when_the_file_record_cannot_be_created(
    db_client: TestClient, storage_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_add(self: FileRepository, file: File) -> File:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(FileRepository, "add", fail_add)
    response = upload(db_client, "s.kml", survey_kml())

    assert response.status_code == 500
    assert "database unavailable" not in response.text
    assert list(storage_dir.iterdir()) == []
