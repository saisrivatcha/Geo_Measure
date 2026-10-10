"""On-disk storage for uploads, one directory per file ID.

    {STORAGE_DIR}/{file_id}/original/   the upload exactly as received
    {STORAGE_DIR}/{file_id}/extracted/  Shapefile components (ZIP uploads only)
    {STORAGE_DIR}/{file_id}/processed/  derived artefacts such as features.geojson

Binaries never go into PostgreSQL; the ``files`` table stores the path of the
original relative to ``STORAGE_DIR`` so the storage root can move.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.security import resolve_within
from app.exceptions import EmptyFileError, FileTooLargeError, StorageError

logger = logging.getLogger(__name__)

UPLOAD_CHUNK_BYTES = 1024 * 1024


PROCESSED_GEOJSON_NAME = "features.geojson"


class Readable(Protocol):
    """A binary stream with ``read(n)`` - e.g. ``UploadFile.file``."""

    def read(self, size: int = -1, /) -> bytes: ...


@dataclass(frozen=True, slots=True)
class StorageLayout:
    root: Path
    original: Path
    extracted: Path
    processed: Path


@dataclass(frozen=True, slots=True)
class StoredUpload:
    path: Path
    size_bytes: int


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def layout_for(self, file_id: uuid.UUID) -> StorageLayout:
        base = self.root / str(file_id)
        return StorageLayout(
            root=base,
            original=base / "original",
            extracted=base / "extracted",
            processed=base / "processed",
        )

    def create_layout(self, file_id: uuid.UUID) -> StorageLayout:
        """Create the directory tree; fails if the file ID directory already exists."""
        layout = self.layout_for(file_id)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            layout.root.mkdir()
            for directory in (layout.original, layout.extracted, layout.processed):
                directory.mkdir()
        except FileExistsError as exc:
            raise StorageError("Storage directory already exists for this file.") from exc
        except OSError as exc:
            raise StorageError() from exc
        return layout

    def save_original(
        self,
        layout: StorageLayout,
        filename: str,
        source: Readable,
        *,
        max_bytes: int,
    ) -> StoredUpload:
        """Stream ``source`` into ``original/`` enforcing ``max_bytes`` as it goes.

        The limit is enforced on bytes received rather than a client-supplied
        Content-Length. ``filename`` must already be sanitised.
        """
        target = resolve_within(layout.original, filename)
        try:
            sink = target.open("xb")
        except OSError as exc:  # includes FileExistsError: never touch an existing file
            raise StorageError() from exc

        size = 0
        try:
            with sink:
                while chunk := source.read(UPLOAD_CHUNK_BYTES):
                    size += len(chunk)
                    if size > max_bytes:
                        raise FileTooLargeError(details={"max_bytes": max_bytes})
                    sink.write(chunk)
        except FileTooLargeError:
            target.unlink(missing_ok=True)
            raise
        except OSError as exc:
            target.unlink(missing_ok=True)
            raise StorageError() from exc

        if size == 0:
            target.unlink(missing_ok=True)
            raise EmptyFileError()
        return StoredUpload(path=target, size_bytes=size)

    def processed_geojson_path(self, layout: StorageLayout) -> Path:
        return layout.processed / PROCESSED_GEOJSON_NAME

    def clear_extracted(self, layout: StorageLayout) -> None:
        """Remove extracted archive members; the original upload is kept."""
        if layout.extracted.exists():
            shutil.rmtree(layout.extracted, ignore_errors=True)
            layout.extracted.mkdir(exist_ok=True)

    def discard(self, layout: StorageLayout) -> None:
        """Remove a layout whose upload was never recorded (no row references it)."""
        shutil.rmtree(layout.root, ignore_errors=True)

    def relative_path(self, path: Path) -> str:
        """Path relative to the storage root, as persisted in the database."""
        return path.resolve().relative_to(self.root).as_posix()
