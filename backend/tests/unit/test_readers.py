from __future__ import annotations

import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from app.exceptions import (
    AmbiguousShapefileError,
    DatasetReadError,
    EmptyDatasetError,
    MissingShapefileComponentsError,
)
from app.geospatial.models import PROPERTIES_COLUMN, SOURCE_FEATURE_ID_COLUMN, SOURCE_LAYER_COLUMN
from app.geospatial.readers import read_kml, read_shapefile_zip
from app.geospatial.validators import FileValidator
from tests.factories import (
    kml_document,
    kml_line,
    kml_placemark,
    kml_point,
    kml_polygon,
    square,
    write_shapefile_zip,
    write_zip,
)

LIMIT = 50 * 1024 * 1024


@pytest.fixture
def validator() -> FileValidator:
    return FileValidator(
        allowed_extensions={".kml", ".zip"}, max_upload_bytes=LIMIT, max_extracted_bytes=LIMIT
    )


def _write(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


# ---- KML -------------------------------------------------------------------------


def test_read_kml_reads_all_folders_in_document_order(tmp_path: Path) -> None:
    document = kml_document(
        (
            "Parcels",
            [
                kml_placemark(
                    "A",
                    kml_polygon([(78.0, 17.0), (78.01, 17.0), (78.01, 17.01), (78.0, 17.0)]),
                    placemark_id="pm-1",
                    data={"owner": "Ravi"},
                ),
                kml_placemark("No geometry", ""),
            ],
        ),
        ("Roads", [kml_placemark("R", kml_line([(78.0, 17.0), (78.1, 17.1)]))]),
    )
    frame = read_kml(_write(tmp_path / "a.kml", document))

    assert list(frame.index) == [0, 1, 2]
    assert frame[SOURCE_LAYER_COLUMN].tolist() == ["Parcels", "Parcels", "Roads"]
    assert frame[SOURCE_FEATURE_ID_COLUMN].tolist()[0] == "pm-1"
    assert frame.geometry.iloc[1] is None
    assert frame.crs.to_epsg() == 4326

    first = frame[PROPERTIES_COLUMN].iloc[0]
    assert first == {"Name": "A", "owner": "Ravi"}  # styling fields and empty columns dropped
    assert frame[PROPERTIES_COLUMN].iloc[2] == {"Name": "R"}  # Roads keep their own schema


def test_read_kml_without_placemarks_is_empty(tmp_path: Path) -> None:
    with pytest.raises(EmptyDatasetError):
        read_kml(_write(tmp_path / "empty.kml", kml_document()))


def test_read_kml_with_placemarks_directly_in_document(tmp_path: Path) -> None:
    document = (
        b'<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        + kml_placemark("P", kml_point(78.4, 17.3)).encode()
        + b"</Document></kml>"
    )
    frame = read_kml(_write(tmp_path / "flat.kml", document))
    assert len(frame) == 1
    assert frame.geometry.iloc[0].equals(Point(78.4, 17.3, 0))


# ---- Shapefile ZIP ---------------------------------------------------------------------


@pytest.fixture
def parcels() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": ["north", "south"], "plots": [3, 5]},
        geometry=[square(500_000, 1_900_000, 100), square(500_000, 1_899_000, 50)],
        crs="EPSG:32643",
    )


def test_read_shapefile_zip(
    tmp_path: Path, parcels: gpd.GeoDataFrame, validator: FileValidator
) -> None:
    archive = write_shapefile_zip(tmp_path, parcels, stem="parcels")
    frame = read_shapefile_zip(archive, tmp_path / "extracted", validator=validator)

    assert frame.crs.to_epsg() == 32643
    assert frame[SOURCE_FEATURE_ID_COLUMN].tolist() == ["0", "1"]
    assert frame[SOURCE_LAYER_COLUMN].tolist() == ["parcels", "parcels"]
    assert frame[PROPERTIES_COLUMN].tolist() == [
        {"name": "north", "plots": 3},
        {"name": "south", "plots": 5},
    ]
    assert frame.geometry.iloc[0].area == pytest.approx(10_000)


def test_missing_prj_reads_with_unknown_crs(
    tmp_path: Path, parcels: gpd.GeoDataFrame, validator: FileValidator
) -> None:
    archive = write_shapefile_zip(tmp_path, parcels, with_prj=False)
    frame = read_shapefile_zip(archive, tmp_path / "extracted", validator=validator)
    assert frame.crs is None
    assert len(frame) == 2


def test_uppercase_extensions_and_nested_folder(
    tmp_path: Path, parcels: gpd.GeoDataFrame, validator: FileValidator
) -> None:
    source = write_shapefile_zip(tmp_path, parcels, stem="roads")

    with zipfile.ZipFile(source) as archive:
        members = {
            f"Export/ROADS{Path(name).suffix.upper()}": archive.read(name)
            for name in archive.namelist()
        }
    upper = write_zip(tmp_path / "upper.zip", members)

    frame = read_shapefile_zip(upper, tmp_path / "extracted", validator=validator)
    assert len(frame) == 2
    assert frame.crs.to_epsg() == 32643  # the .PRJ was matched case-insensitively


@pytest.mark.parametrize("omitted", [".dbf", ".shx"])
def test_missing_required_component(
    tmp_path: Path, parcels: gpd.GeoDataFrame, validator: FileValidator, omitted: str
) -> None:
    archive = write_shapefile_zip(tmp_path, parcels, omit=(omitted,))
    with pytest.raises(MissingShapefileComponentsError) as excinfo:
        read_shapefile_zip(archive, tmp_path / "extracted", validator=validator)
    assert excinfo.value.details["missing"] == [omitted]


def test_two_shapefiles_are_ambiguous(
    tmp_path: Path, parcels: gpd.GeoDataFrame, validator: FileValidator
) -> None:

    first = write_shapefile_zip(tmp_path, parcels, stem="a")
    lines = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:32643")
    second = write_shapefile_zip(tmp_path, lines, stem="b")
    members: dict[str, bytes] = {}
    for archive_path in (first, second):
        with zipfile.ZipFile(archive_path) as archive:
            members.update({name: archive.read(name) for name in archive.namelist()})

    with pytest.raises(AmbiguousShapefileError):
        read_shapefile_zip(
            write_zip(tmp_path / "both.zip", members), tmp_path / "x", validator=validator
        )


def test_corrupt_shapefile_content(tmp_path: Path, validator: FileValidator) -> None:
    archive = write_zip(
        tmp_path / "junk.zip",
        {"junk.shp": b"not a shapefile", "junk.shx": b"nope", "junk.dbf": b"nope"},
    )
    with pytest.raises(DatasetReadError):
        read_shapefile_zip(archive, tmp_path / "extracted", validator=validator)


def test_shapefile_with_no_records_is_empty(tmp_path: Path, validator: FileValidator) -> None:
    empty = gpd.GeoDataFrame({"name": []}, geometry=[], crs="EPSG:4326")
    archive = write_shapefile_zip(tmp_path, empty)
    with pytest.raises(EmptyDatasetError):
        read_shapefile_zip(archive, tmp_path / "extracted", validator=validator)
