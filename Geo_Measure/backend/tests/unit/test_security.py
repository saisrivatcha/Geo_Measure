from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from app.core.security import (
    UnsafePathError,
    normalize_archive_member,
    resolve_within,
    sanitize_filename,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("survey.zip", "survey.zip"),
        ("../../etc/passwd.kml", "passwd.kml"),
        ("C:\\Users\\me\\parcels.zip", "parcels.zip"),
        ("site plan; rm -rf.kml", "site plan_ rm -rf.kml"),
        ("roads\x00.kml", "roads.kml"),
        ("ﬁeld.kml", "field.kml"),  # NFKC ligature normalisation
    ],
)
def test_sanitize_filename(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize("raw", ["", "..", "/", "...", "\x00\x01"])
def test_sanitize_filename_rejects_empty_results(raw: str) -> None:
    with pytest.raises(UnsafePathError):
        sanitize_filename(raw)


def test_sanitize_filename_truncates_but_keeps_extension() -> None:
    result = sanitize_filename("a" * 400 + ".zip")
    assert len(result) == 255
    assert result.endswith(".zip")


@pytest.mark.parametrize(
    ("name", "expected"),
    [("parcels.shp", "parcels.shp"), ("data/./parcels.shp", "data/parcels.shp")],
)
def test_normalize_archive_member_accepts_relative_paths(name: str, expected: str) -> None:
    assert normalize_archive_member(name) == PurePosixPath(expected)


@pytest.mark.parametrize(
    "name",
    ["../evil.shp", "data/../../evil.shp", "/etc/passwd", "..\\evil.shp", "C:/evil.shp", "a\x00b"],
)
def test_normalize_archive_member_rejects_unsafe_paths(name: str) -> None:
    with pytest.raises(UnsafePathError):
        normalize_archive_member(name)


def test_resolve_within_blocks_escape(tmp_path: Path) -> None:
    assert resolve_within(tmp_path, "a", "b.txt") == tmp_path.resolve() / "a" / "b.txt"
    with pytest.raises(UnsafePathError):
        resolve_within(tmp_path, "..", "outside.txt")


def test_resolve_within_blocks_symlink_escape(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    (base / "link").symlink_to(tmp_path)
    with pytest.raises(UnsafePathError):
        resolve_within(base, "link", "outside.txt")
