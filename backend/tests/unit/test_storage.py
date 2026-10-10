from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.exceptions import EmptyFileError, FileTooLargeError, StorageError
from app.services.storage import FileStorage


class ChunkedSource:
    """A stream that returns data in small fixed-size chunks."""

    def __init__(self, payload: bytes, chunk: int = 4) -> None:
        self.payload, self.chunk, self.offset = payload, chunk, 0

    def read(self, size: int = -1, /) -> bytes:
        data = self.payload[self.offset : self.offset + min(self.chunk, size)]
        self.offset += len(data)
        return data


@pytest.fixture
def storage(storage_dir: Path) -> FileStorage:
    return FileStorage(storage_dir)


def test_create_layout_builds_directory_tree(storage: FileStorage, storage_dir: Path) -> None:
    file_id = uuid.uuid4()
    layout = storage.create_layout(file_id)

    assert layout.root == storage_dir.resolve() / str(file_id)
    for directory in (layout.original, layout.extracted, layout.processed):
        assert directory.is_dir()
    assert {p.name for p in layout.root.iterdir()} == {"original", "extracted", "processed"}


def test_create_layout_refuses_existing_id(storage: FileStorage) -> None:
    file_id = uuid.uuid4()
    storage.create_layout(file_id)
    with pytest.raises(StorageError):
        storage.create_layout(file_id)


def test_save_original_streams_to_disk(storage: FileStorage) -> None:
    layout = storage.create_layout(uuid.uuid4())
    stored = storage.save_original(layout, "site.kml", ChunkedSource(b"<kml></kml>"), max_bytes=100)

    assert stored.path == layout.original / "site.kml"
    assert stored.path.read_bytes() == b"<kml></kml>"
    assert stored.size_bytes == 11
    assert storage.relative_path(stored.path) == f"{layout.root.name}/original/site.kml"


def test_save_original_enforces_limit_while_streaming(storage: FileStorage) -> None:
    layout = storage.create_layout(uuid.uuid4())
    with pytest.raises(FileTooLargeError):
        storage.save_original(layout, "big.kml", ChunkedSource(b"x" * 50), max_bytes=10)
    assert list(layout.original.iterdir()) == []


def test_save_original_rejects_empty_stream(storage: FileStorage) -> None:
    layout = storage.create_layout(uuid.uuid4())
    with pytest.raises(EmptyFileError):
        storage.save_original(layout, "empty.kml", ChunkedSource(b""), max_bytes=10)
    assert list(layout.original.iterdir()) == []


def test_save_original_does_not_overwrite(storage: FileStorage) -> None:
    layout = storage.create_layout(uuid.uuid4())
    storage.save_original(layout, "a.kml", ChunkedSource(b"first"), max_bytes=10)
    with pytest.raises(StorageError):
        storage.save_original(layout, "a.kml", ChunkedSource(b"second"), max_bytes=10)
    assert (layout.original / "a.kml").read_bytes() == b"first"


def test_clear_extracted_keeps_original(storage: FileStorage) -> None:
    layout = storage.create_layout(uuid.uuid4())
    storage.save_original(layout, "a.zip", ChunkedSource(b"zip"), max_bytes=10)
    (layout.extracted / "a.shp").write_bytes(b"x")

    storage.clear_extracted(layout)

    assert list(layout.extracted.iterdir()) == []
    assert (layout.original / "a.zip").exists()
