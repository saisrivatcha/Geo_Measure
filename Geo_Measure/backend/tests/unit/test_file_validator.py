from __future__ import annotations

import warnings
import zipfile
from pathlib import Path

import pytest

from app.db.models import FileType
from app.exceptions import (
    AmbiguousShapefileError,
    EmptyFileError,
    FileTooLargeError,
    InvalidArchiveError,
    InvalidFilenameError,
    InvalidFileTypeError,
    InvalidKMLError,
    MissingShapefileComponentsError,
    UnsafeArchiveError,
)
from app.geospatial.validators import FileValidator
from tests.factories import VALID_KML, shapefile_members, write_symlink_zip, write_zip

MAX_UPLOAD = 1024
MAX_EXTRACTED = 4096


@pytest.fixture
def validator() -> FileValidator:
    return FileValidator(
        allowed_extensions={".kml", ".zip"},
        max_upload_bytes=MAX_UPLOAD,
        max_extracted_bytes=MAX_EXTRACTED,
        max_archive_members=20,
    )


# ---- filename & extension ------------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "file_type"),
    [("site.kml", FileType.KML), ("SITE.KML", FileType.KML), ("parcels.zip", FileType.SHAPEFILE)],
)
def test_accepts_supported_extensions(
    validator: FileValidator, filename: str, file_type: FileType
) -> None:
    result = validator.validate_upload(filename)
    assert result.file_type is file_type
    assert result.filename == filename


@pytest.mark.parametrize(
    "filename", ["roads.geojson", "malware.exe", "notes.txt", "README", "parcels.shp"]
)
def test_rejects_unsupported_extensions(validator: FileValidator, filename: str) -> None:
    with pytest.raises(InvalidFileTypeError) as excinfo:
        validator.validate_upload(filename)
    assert excinfo.value.code == "INVALID_FILE_TYPE"
    assert excinfo.value.details["allowed"] == [".kml", ".zip"]


def test_rejects_kmz_with_specific_message(validator: FileValidator) -> None:
    with pytest.raises(InvalidFileTypeError, match="KMZ"):
        validator.validate_upload("tour.kmz")


def test_respects_configured_extension_subset() -> None:
    kml_only = FileValidator(
        allowed_extensions={".kml"}, max_upload_bytes=MAX_UPLOAD, max_extracted_bytes=MAX_EXTRACTED
    )
    with pytest.raises(InvalidFileTypeError):
        kml_only.validate_upload("parcels.zip")


@pytest.mark.parametrize("filename", [None, "", "..", "/"])
def test_rejects_missing_or_unusable_filenames(
    validator: FileValidator, filename: str | None
) -> None:
    with pytest.raises(InvalidFilenameError):
        validator.validate_upload(filename)


def test_path_traversal_filename_is_reduced_to_basename(validator: FileValidator) -> None:
    assert validator.validate_upload("../../etc/cron.d/site.kml").filename == "site.kml"


# ---- size ------------------------------------------------------------------------


def test_rejects_empty_file(validator: FileValidator) -> None:
    with pytest.raises(EmptyFileError):
        validator.validate_upload("site.kml", size_bytes=0)


def test_rejects_file_over_limit(validator: FileValidator) -> None:
    with pytest.raises(FileTooLargeError) as excinfo:
        validator.validate_upload("site.kml", size_bytes=MAX_UPLOAD + 1)
    assert excinfo.value.details == {"size_bytes": MAX_UPLOAD + 1, "max_bytes": MAX_UPLOAD}
    assert excinfo.value.status_code == 413


def test_accepts_file_exactly_at_limit(validator: FileValidator) -> None:
    validator.validate_upload("site.kml", size_bytes=MAX_UPLOAD)


# ---- KML content -----------------------------------------------------------------


def test_accepts_valid_kml(validator: FileValidator, tmp_path: Path) -> None:
    path = tmp_path / "site.kml"
    path.write_bytes(VALID_KML)
    validator.validate_kml(path)


@pytest.mark.parametrize(
    ("content", "match"),
    [
        (b"<gpx><trk/></gpx>", "root element is not <kml>"),
        (b"<kml><Document>", "not well-formed"),
        (b"PK\x03\x04 binary", "not well-formed"),
        (
            b'<?xml version="1.0"?><!DOCTYPE kml [<!ENTITY a "aaaa">]><kml>&a;</kml>',
            "DTD",
        ),
        (b'<!DOCTYPE kml SYSTEM "file:///etc/passwd"><kml/>', "DTD"),
    ],
)
def test_rejects_invalid_kml(
    validator: FileValidator, tmp_path: Path, content: bytes, match: str
) -> None:
    path = tmp_path / "bad.kml"
    path.write_bytes(content)
    with pytest.raises(InvalidKMLError, match=match):
        validator.validate_kml(path)


# ---- Shapefile ZIP ---------------------------------------------------------------


def test_selects_single_shapefile(validator: FileValidator, tmp_path: Path) -> None:
    archive = write_zip(tmp_path / "a.zip", shapefile_members("parcels"))
    bundle = validator.inspect_shapefile_archive(archive)
    assert bundle.stem == "parcels"
    assert set(bundle.members) == {".shp", ".shx", ".dbf", ".prj"}
    assert bundle.has_prj


def test_accepts_shapefile_inside_a_folder_and_ignores_os_noise(
    validator: FileValidator, tmp_path: Path
) -> None:
    members = {
        **shapefile_members("roads", prefix="export/"),
        "__MACOSX/export/._roads.shp": b"x",
        "export/.DS_Store": b"x",
        "export/readme.txt": b"notes",
    }
    bundle = validator.inspect_shapefile_archive(write_zip(tmp_path / "a.zip", members))
    assert bundle.members[".shp"] == "export/roads.shp"


def test_component_extensions_are_case_insensitive(
    validator: FileValidator, tmp_path: Path
) -> None:
    members = {"Parcels.SHP": b"x", "Parcels.shx": b"x", "parcels.DBF": b"x"}
    bundle = validator.inspect_shapefile_archive(write_zip(tmp_path / "a.zip", members))
    assert set(bundle.members) == {".shp", ".shx", ".dbf"}


def test_missing_prj_is_allowed_and_reported(validator: FileValidator, tmp_path: Path) -> None:
    archive = write_zip(tmp_path / "a.zip", shapefile_members(with_prj=False))
    assert validator.inspect_shapefile_archive(archive).has_prj is False


def test_rejects_malformed_zip(validator: FileValidator, tmp_path: Path) -> None:
    path = tmp_path / "broken.zip"
    path.write_bytes(b"PK\x03\x04 this is not really a zip")
    with pytest.raises(InvalidArchiveError) as excinfo:
        validator.inspect_shapefile_archive(path)
    assert excinfo.value.code == "INVALID_ARCHIVE"


def test_rejects_zip_without_shp(validator: FileValidator, tmp_path: Path) -> None:
    archive = write_zip(tmp_path / "a.zip", {"parcels.dbf": b"x", "notes.txt": b"x"})
    with pytest.raises(MissingShapefileComponentsError) as excinfo:
        validator.inspect_shapefile_archive(archive)
    assert excinfo.value.details["missing"] == [".shp"]


@pytest.mark.parametrize(
    ("omitted", "missing"),
    [({".shx"}, [".shx"]), ({".dbf"}, [".dbf"]), ({".shx", ".dbf"}, [".shx", ".dbf"])],
)
def test_rejects_missing_required_components(
    validator: FileValidator, tmp_path: Path, omitted: set[str], missing: list[str]
) -> None:
    members = {
        name: data for name, data in shapefile_members().items() if Path(name).suffix not in omitted
    }
    with pytest.raises(MissingShapefileComponentsError) as excinfo:
        validator.inspect_shapefile_archive(write_zip(tmp_path / "a.zip", members))
    assert excinfo.value.details["missing"] == missing
    assert excinfo.value.code == "MISSING_SHAPEFILE_COMPONENTS"


def test_components_must_share_the_same_folder(validator: FileValidator, tmp_path: Path) -> None:
    members = {"a/parcels.shp": b"x", "b/parcels.shx": b"x", "b/parcels.dbf": b"x"}
    with pytest.raises(MissingShapefileComponentsError):
        validator.inspect_shapefile_archive(write_zip(tmp_path / "a.zip", members))


def test_rejects_ambiguous_multiple_shapefiles(validator: FileValidator, tmp_path: Path) -> None:
    members = {**shapefile_members("roads"), **shapefile_members("rivers")}
    with pytest.raises(AmbiguousShapefileError) as excinfo:
        validator.inspect_shapefile_archive(write_zip(tmp_path / "a.zip", members))
    assert excinfo.value.details["candidates"] == ["rivers.shp", "roads.shp"]


@pytest.mark.parametrize(
    "evil_name",
    ["../evil.shp", "data/../../evil.shp", "/etc/cron.d/evil", "..\\..\\evil.dbf", "C:/evil.shp"],
)
def test_rejects_path_traversal_members(
    validator: FileValidator, tmp_path: Path, evil_name: str
) -> None:
    members = {**shapefile_members(), evil_name: b"payload"}
    with pytest.raises(UnsafeArchiveError) as excinfo:
        validator.inspect_shapefile_archive(write_zip(tmp_path / "a.zip", members))
    assert excinfo.value.code == "UNSAFE_ARCHIVE"


def test_rejects_symlink_members(validator: FileValidator, tmp_path: Path) -> None:
    archive = write_symlink_zip(tmp_path / "a.zip", "parcels.shp", "/etc/passwd")
    with pytest.raises(UnsafeArchiveError, match="symbolic links"):
        validator.inspect_shapefile_archive(archive)


@pytest.mark.parametrize("duplicate", ["parcels.shp", "PARCELS.SHP"])
def test_rejects_duplicate_members_that_would_overwrite(
    validator: FileValidator, tmp_path: Path, duplicate: str
) -> None:
    archive = write_zip(tmp_path / "a.zip", shapefile_members())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # zipfile warns on exact duplicate names
        with zipfile.ZipFile(archive, "a") as handle:
            handle.writestr(duplicate, b"second copy")
    with pytest.raises(UnsafeArchiveError, match="duplicate"):
        validator.inspect_shapefile_archive(archive)


def test_rejects_too_many_members(validator: FileValidator, tmp_path: Path) -> None:
    members = {**shapefile_members(), **{f"junk/{i}.txt": b"" for i in range(30)}}
    with pytest.raises(UnsafeArchiveError, match="too many"):
        validator.inspect_shapefile_archive(write_zip(tmp_path / "a.zip", members))


def test_rejects_archive_declaring_oversized_contents(
    validator: FileValidator, tmp_path: Path
) -> None:
    members = {**shapefile_members(), "parcels.dbf": b"\0" * (MAX_EXTRACTED + 1)}
    with pytest.raises(UnsafeArchiveError, match="expands beyond"):
        validator.inspect_shapefile_archive(write_zip(tmp_path / "bomb.zip", members))


def test_rejects_empty_archive(validator: FileValidator, tmp_path: Path) -> None:
    with pytest.raises(InvalidArchiveError, match="no files"):
        validator.inspect_shapefile_archive(write_zip(tmp_path / "a.zip", {}))
