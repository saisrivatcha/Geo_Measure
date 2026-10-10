"""Validation: uploads before any GDAL reader runs, and geometries before measurement.

The validator works in two stages:

1. :meth:`FileValidator.validate_upload` - cheap checks on client metadata
   (filename, extension, declared size) before bytes are written to disk.
2. :meth:`FileValidator.validate_kml` / :meth:`FileValidator.inspect_shapefile_archive`
   - content checks on the stored file. The archive inspection reads only the
   ZIP central directory; nothing is extracted until it passes.
"""

from __future__ import annotations

import logging
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from xml.parsers import expat

import numpy as np
import shapely
from shapely.geometry.base import BaseGeometry

from app.core.security import UnsafePathError, normalize_archive_member, sanitize_filename
from app.db.models.enums import FileType
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

logger = logging.getLogger(__name__)

EXTENSION_FILE_TYPES: Mapping[str, FileType] = {
    ".kml": FileType.KML,
    ".zip": FileType.SHAPEFILE,
}
REQUIRED_SHAPEFILE_EXTENSIONS: tuple[str, ...] = (".shp", ".shx", ".dbf")
OPTIONAL_SHAPEFILE_EXTENSIONS: tuple[str, ...] = (".prj", ".cpg")
SHAPEFILE_EXTENSIONS = REQUIRED_SHAPEFILE_EXTENSIONS + OPTIONAL_SHAPEFILE_EXTENSIONS

DEFAULT_MAX_ARCHIVE_MEMBERS = 500
KML_PARSE_CHUNK_BYTES = 64 * 1024

_ZIP_FLAG_ENCRYPTED = 0x1
_UNIX_FILE_TYPE_MASK = 0o170000
_UNIX_SYMLINK = 0o120000
_ARCHIVE_NOISE_PREFIXES = ("__MACOSX/",)
_ARCHIVE_NOISE_NAMES = frozenset({".ds_store", "thumbs.db"})


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    filename: str
    extension: str
    file_type: FileType


@dataclass(frozen=True, slots=True)
class ShapefileBundle:
    """The single Shapefile dataset selected from an archive.

    ``members`` maps a lowercase component extension (``.shp``) to the original
    member name inside the ZIP.
    """

    stem: str
    members: Mapping[str, str] = field(repr=False)

    @property
    def has_prj(self) -> bool:
        return ".prj" in self.members


class FileValidator:
    """Validates uploaded KML documents and Shapefile ZIP archives."""

    def __init__(
        self,
        *,
        allowed_extensions: Iterable[str],
        max_upload_bytes: int,
        max_extracted_bytes: int,
        max_archive_members: int = DEFAULT_MAX_ARCHIVE_MEMBERS,
    ) -> None:
        self.allowed_extensions = frozenset(ext.lower() for ext in allowed_extensions)
        self.max_upload_bytes = max_upload_bytes
        self.max_extracted_bytes = max_extracted_bytes
        self.max_archive_members = max_archive_members

    # ---- stage 1: metadata ------------------------------------------------

    def validate_upload(
        self, filename: str | None, size_bytes: int | None = None
    ) -> ValidatedUpload:
        """Validate the client filename and, when known, the declared size."""
        if not filename:
            raise InvalidFilenameError("The upload has no filename.")
        try:
            safe_name = sanitize_filename(filename)
        except UnsafePathError as exc:
            raise InvalidFilenameError(details={"filename": filename}) from exc

        extension = PurePosixPath(safe_name).suffix.lower()
        if extension == ".kmz":
            raise InvalidFileTypeError(
                "KMZ archives are not supported. Extract the .kml and upload it directly.",
                details={"extension": extension, "allowed": sorted(self.allowed_extensions)},
            )
        if extension not in self.allowed_extensions or extension not in EXTENSION_FILE_TYPES:
            raise InvalidFileTypeError(
                details={"extension": extension or None, "allowed": sorted(self.allowed_extensions)}
            )
        if size_bytes is not None:
            self.validate_size(size_bytes)
        return ValidatedUpload(safe_name, extension, EXTENSION_FILE_TYPES[extension])

    def validate_size(self, size_bytes: int) -> None:
        if size_bytes <= 0:
            raise EmptyFileError()
        if size_bytes > self.max_upload_bytes:
            raise FileTooLargeError(
                details={"size_bytes": size_bytes, "max_bytes": self.max_upload_bytes}
            )

    # ---- stage 2: content -------------------------------------------------

    def validate_kml(self, path: Path) -> None:
        """Confirm the document is well-formed XML with a ``<kml>`` root element.

        DTDs and entity declarations are rejected outright: KML never needs them
        and they are the vehicle for entity-expansion and XXE attacks.
        """
        _check_kml_document(path)

    def inspect_shapefile_archive(self, path: Path) -> ShapefileBundle:
        """Validate the ZIP central directory and select exactly one Shapefile."""
        try:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError) as exc:
            raise InvalidArchiveError() from exc

        entries = self._safe_file_entries(infos)
        if not entries:
            raise InvalidArchiveError("The archive contains no files.")

        bundle = self._select_bundle(entries)
        logger.info(
            "upload.archive_inspected",
            extra={
                "shapefile": bundle.stem,
                "components": sorted(bundle.members),
                "has_prj": bundle.has_prj,
            },
        )
        return bundle

    # ---- archive helpers --------------------------------------------------

    def _safe_file_entries(self, infos: list[zipfile.ZipInfo]) -> list[_ArchiveEntry]:
        if len(infos) > self.max_archive_members:
            raise UnsafeArchiveError(
                "The archive contains too many entries.",
                details={"entries": len(infos), "max_entries": self.max_archive_members},
            )

        entries: list[_ArchiveEntry] = []
        seen: set[str] = set()
        total_bytes = 0
        for info in infos:
            try:
                relative = normalize_archive_member(info.filename)
            except UnsafePathError as exc:
                raise UnsafeArchiveError(details={"member": info.filename}) from exc

            if _is_symlink(info):
                raise UnsafeArchiveError(
                    "The archive contains symbolic links.", details={"member": info.filename}
                )
            if info.is_dir() or _is_archive_noise(relative):
                continue
            if info.flag_bits & _ZIP_FLAG_ENCRYPTED:
                raise InvalidArchiveError(
                    "Encrypted archives are not supported.", details={"member": info.filename}
                )

            key = relative.as_posix().lower()
            if key in seen:
                raise UnsafeArchiveError(
                    "The archive contains duplicate entries.", details={"member": info.filename}
                )
            seen.add(key)

            total_bytes += info.file_size
            if total_bytes > self.max_extracted_bytes:
                raise UnsafeArchiveError(
                    "The archive expands beyond the allowed size.",
                    details={"max_extracted_bytes": self.max_extracted_bytes},
                )
            entries.append(_ArchiveEntry(info.filename, relative, info.file_size))
        return entries

    def _select_bundle(self, entries: list[_ArchiveEntry]) -> ShapefileBundle:
        groups: dict[tuple[str, str], dict[str, _ArchiveEntry]] = defaultdict(dict)
        for entry in entries:
            extension = entry.path.suffix.lower()
            if extension in SHAPEFILE_EXTENSIONS:
                group_key = (entry.path.parent.as_posix().lower(), entry.path.stem.lower())
                groups[group_key][extension] = entry

        candidates = {key: parts for key, parts in groups.items() if ".shp" in parts}
        if not candidates:
            raise MissingShapefileComponentsError(
                "The archive does not contain a .shp file.",
                details={"missing": [".shp"]},
            )
        if len(candidates) > 1:
            raise AmbiguousShapefileError(
                details={
                    "candidates": sorted(
                        parts[".shp"].path.as_posix() for parts in candidates.values()
                    )
                }
            )

        (parts,) = candidates.values()
        shp_path = parts[".shp"].path
        missing = [ext for ext in REQUIRED_SHAPEFILE_EXTENSIONS if ext not in parts]
        if missing:
            raise MissingShapefileComponentsError(
                f"Shapefile '{shp_path.as_posix()}' is missing: {', '.join(missing)}.",
                details={"shapefile": shp_path.as_posix(), "missing": missing},
            )

        return ShapefileBundle(
            stem=shp_path.stem,
            members={ext: entry.name for ext, entry in parts.items()},
        )


@dataclass(frozen=True, slots=True)
class _ArchiveEntry:
    name: str
    path: PurePosixPath
    size: int


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & _UNIX_FILE_TYPE_MASK == _UNIX_SYMLINK


def _is_archive_noise(path: PurePosixPath) -> bool:
    posix = path.as_posix()
    return (
        posix.startswith(_ARCHIVE_NOISE_PREFIXES)
        or path.name.lower() in _ARCHIVE_NOISE_NAMES
        or path.name.startswith("._")
    )


def _check_kml_document(path: Path) -> None:
    """Stream-parse the whole document with expat (bounded memory)."""
    parser = expat.ParserCreate(namespace_separator=" ")
    root: list[str] = []

    def reject_dtd(*_args: object) -> None:
        raise InvalidKMLError("KML documents must not declare a DTD or entities.")

    def on_start(tag: str, _attrs: object) -> None:
        if root:
            return
        local_name = tag.rsplit(" ", 1)[-1]
        if local_name != "kml":
            raise InvalidKMLError(
                "The document root element is not <kml>.", details={"root": local_name}
            )
        root.append(local_name)

    parser.StartDoctypeDeclHandler = reject_dtd
    parser.EntityDeclHandler = reject_dtd
    parser.StartElementHandler = on_start

    try:
        with path.open("rb") as handle:
            while chunk := handle.read(KML_PARSE_CHUNK_BYTES):
                parser.Parse(chunk, False)
            parser.Parse(b"", True)
    except expat.ExpatError as exc:
        raise InvalidKMLError(
            "The KML document is not well-formed XML.",
            details={"line": exc.lineno, "reason": expat.ErrorString(exc.code)},
        ) from exc


# ---- geometry validity -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class GeometryValidation:
    """Vectorised validity results, aligned with the input array.

    ``measurable`` holds the geometry to measure: the original when valid, the
    repaired version when repair succeeded, ``None`` when unrepairable. The
    original array is never modified, so clients still see the source geometry.
    """

    valid: np.ndarray  # bool
    repaired: np.ndarray  # bool
    unrepairable: np.ndarray  # bool
    reasons: np.ndarray  # object: str | None (validity reason for unrepairable rows)
    measurable: np.ndarray  # object: shapely geometry | None


def validate_and_repair(geometries: np.ndarray, families: np.ndarray) -> GeometryValidation:
    """Check OGC validity and attempt a family-preserving repair of invalid rows.

    ``families`` gives each row's expected family (``"polygonal"`` or
    ``"linear"``). Repair uses GEOS ``make_valid`` with the *structure* method,
    which rebuilds polygons from their rings (e.g. a self-intersecting bow-tie
    becomes two triangles) and drops collapsed parts. A repair is accepted only
    if the result is non-empty, valid and of the same family - a polygon that
    collapses to a line is not a polygon any more and must not be measured as one.
    """
    valid = shapely.is_valid(geometries)
    repaired = np.zeros(len(geometries), dtype=bool)
    unrepairable = np.zeros(len(geometries), dtype=bool)
    reasons = np.full(len(geometries), None, dtype=object)
    measurable = geometries.copy()

    for index in np.flatnonzero(~valid):
        original = geometries[index]
        candidate = _repair(original, families[index])
        if candidate is None:
            unrepairable[index] = True
            reasons[index] = shapely.is_valid_reason(original)
            measurable[index] = None
        else:
            repaired[index] = True
            measurable[index] = candidate
    return GeometryValidation(valid, repaired, unrepairable, reasons, measurable)


_POLYGONAL_TYPES = frozenset({"Polygon", "MultiPolygon"})
_LINEAR_TYPES = frozenset({"LineString", "MultiLineString", "LinearRing"})


def _repair(geometry: BaseGeometry, family: str) -> BaseGeometry | None:
    try:
        candidate = shapely.make_valid(geometry, method="structure", keep_collapsed=False)
    except shapely.errors.GEOSException:
        return None
    if candidate is None or candidate.is_empty:
        return None

    allowed = _POLYGONAL_TYPES if family == "polygonal" else _LINEAR_TYPES
    if candidate.geom_type == "GeometryCollection":
        parts = [part for part in shapely.get_parts(candidate) if part.geom_type in allowed]
        if not parts:
            return None
        candidate = shapely.union_all(parts)
    if candidate.geom_type not in allowed or candidate.is_empty or not candidate.is_valid:
        return None
    return candidate
