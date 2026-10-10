"""End-to-end checks on the committed fixture datasets (tests/fixtures).

Expected areas and lengths for lon/lat data come from pyproj's geodesic
calculations on the WGS 84 ellipsoid: an independent reference that does not
use any projection, so agreement shows the projected measurement is right.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pyproj import Geod
from shapely.geometry import LineString, MultiLineString, Polygon

from tests.fixtures import (
    LINE_4326,
    MIXED_FEATURES,
    POINT_4326,
    POLYGON_4326,
    PROJECTED_POLYGON_AREAS,
    PROJECTED_POLYGON_CRS,
    projected_polygon_zip,
)

pytestmark = pytest.mark.db

GEOD = Geod(ellps="WGS84")
TOLERANCE = 1e-3  # 0.1 %, the measurement CRS distortion limit


def upload(client: TestClient, path: Path) -> dict[str, Any]:
    response = client.post("/api/files/", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 201, response.text
    return response.json()


def features(client: TestClient, file_id: str) -> list[dict[str, Any]]:
    return client.get(f"/api/files/{file_id}/measurements/", params={"page_size": 500}).json()[
        "features"
    ]


def geodesic_area(ring: list[tuple[float, float]]) -> float:
    area, _ = GEOD.geometry_area_perimeter(Polygon(ring))
    return abs(area)


def test_polygon_4326_is_projected_then_measured_in_square_metres(db_client: TestClient) -> None:
    body = upload(db_client, POLYGON_4326)
    file = body["file"]

    assert file["source_crs"] == "EPSG:4326"
    assert file["measurement_crs"] == "EPSG:32644"  # UTM zone of the data, not a constant
    assert file["measurement_crs_name"] == "WGS 84 / UTM zone 44N"

    (feature,) = features(db_client, file["id"])
    expected = geodesic_area([(78.48, 17.38), (78.49, 17.38), (78.49, 17.39), (78.48, 17.39)])
    assert feature["measurement"]["unit"] == "square_meters"
    assert feature["measurement"]["value"] == pytest.approx(expected, rel=TOLERANCE)
    assert feature["measurement"]["value"] != pytest.approx(0.0001)  # not degrees²
    assert feature["source_feature_id"] == "parcel-1"
    assert feature["properties"] == {
        "Name": "Parcel 1",
        "owner": "Survey Office",
        "survey_no": "331",
    }


def test_line_4326_length_matches_geodesic_length(db_client: TestClient) -> None:
    file = upload(db_client, LINE_4326)["file"]
    (feature,) = features(db_client, file["id"])

    expected = GEOD.geometry_length(LineString([(78.40, 17.30), (78.45, 17.36), (78.52, 17.40)]))
    assert feature["measurement"]["type"] == "LENGTH"
    assert feature["measurement"]["unit"] == "meters"
    assert feature["measurement"]["value"] == pytest.approx(expected, rel=TOLERANCE)


def test_point_4326_needs_no_measurement(db_client: TestClient) -> None:
    body = upload(db_client, POINT_4326)
    assert body["file"]["measurement_crs"] is None  # nothing to measure, so no CRS chosen
    assert body["summary"]["not_required_features"] == 2
    for feature in features(db_client, body["file"]["id"]):
        assert feature["measurement_status"] == "NOT_REQUIRED"
        assert feature["measurement"] is None


def test_projected_polygon_is_measured_in_its_own_crs(
    db_client: TestClient, tmp_path: Path
) -> None:
    file = upload(db_client, projected_polygon_zip(tmp_path))["file"]

    assert (file["source_crs"], file["measurement_crs"]) == (
        PROJECTED_POLYGON_CRS,
        PROJECTED_POLYGON_CRS,
    )
    values = [f["measurement"]["value"] for f in features(db_client, file["id"])]
    assert values == pytest.approx(PROJECTED_POLYGON_AREAS)


def test_projected_polygon_without_prj_is_not_measured(
    db_client: TestClient, tmp_path: Path
) -> None:
    file = upload(db_client, projected_polygon_zip(tmp_path, with_prj=False))["file"]
    assert file["status"] == "COMPLETED"
    assert file["source_crs"] is None
    statuses = {f["measurement_status"] for f in features(db_client, file["id"])}
    assert statuses == {"CRS_UNAVAILABLE"}


def test_mixed_features_each_case_is_handled_without_failing_the_file(
    db_client: TestClient,
) -> None:
    body = upload(db_client, MIXED_FEATURES)
    assert body["file"]["status"] == "COMPLETED"
    assert body["file"]["feature_count"] == 9

    by_id = {f["source_feature_id"]: f for f in features(db_client, body["file"]["id"])}
    null_feature = next(f for f in by_id.values() if f["geometry_type"] is None)

    expected_status = {
        "polygon": ("Polygon", "COMPLETED", "AREA"),
        "multipolygon": ("MultiPolygon", "COMPLETED", "AREA"),
        "line": ("LineString", "COMPLETED", "LENGTH"),
        "multiline": ("MultiLineString", "COMPLETED", "LENGTH"),
        "point": ("Point", "NOT_REQUIRED", None),
        "collection": ("GeometryCollection", "NOT_SUPPORTED", None),
        "empty": ("LineString", "NO_GEOMETRY", None),
        "bowtie": ("Polygon", "COMPLETED", "AREA"),
    }
    for source_id, (geometry_type, status, measurement_type) in expected_status.items():
        feature = by_id[source_id]
        assert feature["geometry_type"] == geometry_type, source_id
        assert feature["measurement_status"] == status, source_id
        measured_type = feature["measurement"]["type"] if feature["measurement"] else None
        assert measured_type == measurement_type, source_id
    assert null_feature["measurement_status"] == "NO_GEOMETRY"

    multipolygon = by_id["multipolygon"]["measurement"]["value"]
    parts = [
        geodesic_area([(78.50, 17.38), (78.505, 17.38), (78.505, 17.385), (78.50, 17.385)]),
        geodesic_area([(78.51, 17.38), (78.515, 17.38), (78.515, 17.385), (78.51, 17.385)]),
    ]
    assert multipolygon == pytest.approx(sum(parts), rel=TOLERANCE)

    multiline = by_id["multiline"]["measurement"]["value"]
    expected_multiline = GEOD.geometry_length(
        MultiLineString([[(78.40, 17.40), (78.42, 17.40)], [(78.40, 17.41), (78.42, 17.41)]])
    )
    assert multiline == pytest.approx(expected_multiline, rel=TOLERANCE)

    bowtie = by_id["bowtie"]
    assert (bowtie["geometry_valid"], bowtie["geometry_repaired"]) == (False, True)
    # Repaired into two triangles: half the 0.01 x 0.01 degree square.
    square = geodesic_area([(78.60, 17.38), (78.61, 17.38), (78.61, 17.39), (78.60, 17.39)])
    assert bowtie["measurement"]["value"] == pytest.approx(square / 2, rel=5e-3)

    summary = body["summary"]
    assert summary["measured_features"] == 5
    assert summary["unsupported_features"] == 1
    assert summary["no_geometry_features"] == 2
    # Breakdown by type: the null geometry belongs to no type.
    assert (summary["polygon_count"], summary["line_count"], summary["point_count"]) == (3, 3, 1)
    assert summary["other_count"] == 1


def test_mixed_features_geojson_is_wgs84_and_complete(db_client: TestClient) -> None:
    file_id = upload(db_client, MIXED_FEATURES)["file"]["id"]
    body = db_client.get(f"/api/files/{file_id}/geojson").json()

    assert body["metadata"]["total_features"] == 9
    assert body["metadata"]["truncated"] is False
    assert body["metadata"]["features_without_geometry"] == 2
    polygon = body["features"][0]
    assert polygon["geometry"]["type"] == "Polygon"
    assert polygon["geometry"]["coordinates"][0][0][:2] == [78.48, 17.38]
    assert polygon["geomeasure"]["measurement_type"] == "AREA"
