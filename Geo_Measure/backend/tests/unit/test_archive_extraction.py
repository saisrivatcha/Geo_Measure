from __future__ import annotations

from pathlib import Path

import pyogrio
import pytest

from app.exceptions import UnsafeArchiveError
from app.geospatial.archive import extract_shapefile_bundle
from app.geospatial.validators import FileValidator
from tests.factories import build_real_shapefile_zip, shapefile_members, write_zip

LIMIT = 10 * 1024 * 1024


@pytest.fixture
def validator() -> FileValidator:
    return FileValidator(
        allowed_extensions={".kml", ".zip"}, max_upload_bytes=LIMIT, max_extracted_bytes=LIMIT
    )


def test_extracts_only_bundle_components_flat(validator: FileValidator, tmp_path: Path) -> None:
    archive = write_zip(
        tmp_path / "a.zip",
        {**shapefile_members("roads", prefix="nested/dir/"), "nested/run.sh": b"#!/bin/sh"},
    )
    bundle = validator.inspect_shapefile_archive(archive)
    destination = tmp_path / "extracted"

    written = extract_shapefile_bundle(archive, bundle, destination, max_extracted_bytes=LIMIT)

    assert sorted(path.name for path in destination.iterdir()) == [
        "roads.dbf",
        "roads.prj",
        "roads.shp",
        "roads.shx",
    ]
    assert written[".shp"] == destination.resolve() / "roads.shp"


def test_extracted_real_shapefile_is_readable_by_gdal(
    validator: FileValidator, tmp_path: Path
) -> None:
    archive = build_real_shapefile_zip(tmp_path)
    bundle = validator.inspect_shapefile_archive(archive)
    written = extract_shapefile_bundle(archive, bundle, tmp_path / "out", max_extracted_bytes=LIMIT)

    info = pyogrio.read_info(written[".shp"])
    assert info["features"] == 1
    assert info["geometry_type"] == "Polygon"
    assert "4326" in info["crs"]


def test_missing_prj_extracts_with_undefined_crs(validator: FileValidator, tmp_path: Path) -> None:
    archive = build_real_shapefile_zip(tmp_path, with_prj=False)
    bundle = validator.inspect_shapefile_archive(archive)
    written = extract_shapefile_bundle(archive, bundle, tmp_path / "out", max_extracted_bytes=LIMIT)

    assert ".prj" not in written
    assert pyogrio.read_info(written[".shp"])["crs"] is None


def test_never_overwrites_existing_files(validator: FileValidator, tmp_path: Path) -> None:
    archive = write_zip(tmp_path / "a.zip", shapefile_members())
    bundle = validator.inspect_shapefile_archive(archive)
    destination = tmp_path / "extracted"
    destination.mkdir()
    existing = destination / "parcels.shp"
    existing.write_bytes(b"original")

    with pytest.raises(UnsafeArchiveError):
        extract_shapefile_bundle(archive, bundle, destination, max_extracted_bytes=LIMIT)

    assert existing.read_bytes() == b"original"
    assert sorted(path.name for path in destination.iterdir()) == ["parcels.shp"]


def test_enforces_actual_decompressed_size(validator: FileValidator, tmp_path: Path) -> None:
    # Highly compressible payload: a few KB on disk, 2 MB once decompressed.
    members = {**shapefile_members(), "parcels.dbf": b"\0" * (2 * 1024 * 1024)}
    archive = write_zip(tmp_path / "bomb.zip", members)
    bundle = validator.inspect_shapefile_archive(archive)
    destination = tmp_path / "extracted"

    with pytest.raises(UnsafeArchiveError, match="expands beyond"):
        extract_shapefile_bundle(archive, bundle, destination, max_extracted_bytes=1024 * 1024)

    assert list(destination.iterdir()) == []
