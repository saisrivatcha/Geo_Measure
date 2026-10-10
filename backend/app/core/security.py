"""Filesystem safety primitives for untrusted names and paths.

Everything here is pure and side-effect free so it can be unit tested in
isolation and reused by upload handling and archive extraction.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path, PurePosixPath

MAX_FILENAME_LENGTH = 255

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._\- ()]+")


class UnsafePathError(ValueError):
    """Raised when a name or path could escape its intended directory."""


def sanitize_filename(raw_name: str) -> str:
    """Reduce an untrusted client filename to a safe basename.

    Directory components (``/`` or ``\\``) are dropped, Unicode is normalised,
    control and shell-hostile characters are replaced, and the result is
    truncated while keeping the extension.
    """
    basename = raw_name.replace("\\", "/").rsplit("/", 1)[-1]
    normalized = unicodedata.normalize("NFKC", basename)
    printable = "".join(ch for ch in normalized if unicodedata.category(ch)[0] != "C")
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", printable).strip(" .")
    if not cleaned or cleaned.strip("_") == "":
        raise UnsafePathError("Filename is empty after sanitisation")

    if len(cleaned) > MAX_FILENAME_LENGTH:
        path = PurePosixPath(cleaned)
        suffix = path.suffix[:16]
        cleaned = path.stem[: MAX_FILENAME_LENGTH - len(suffix)] + suffix
    return cleaned


def normalize_archive_member(name: str) -> PurePosixPath:
    """Validate an archive member name and return it as a relative POSIX path.

    Rejects absolute paths, Windows drive letters, NUL bytes and any ``..``
    component. Backslashes are treated as separators so ``..\\evil`` is caught.
    """
    if not name or "\x00" in name:
        raise UnsafePathError("Archive member has an empty or invalid name")

    unified = name.replace("\\", "/")
    if unified.startswith("/") or _WINDOWS_DRIVE.match(unified):
        raise UnsafePathError(f"Archive member uses an absolute path: {name!r}")

    parts = [part for part in unified.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise UnsafePathError(f"Archive member escapes the archive root: {name!r}")
    if not parts:
        raise UnsafePathError(f"Archive member has no usable path: {name!r}")
    return PurePosixPath(*parts)


def resolve_within(base_dir: Path, *parts: str) -> Path:
    """Join ``parts`` onto ``base_dir`` and guarantee the result stays inside it.

    Symlinks are resolved before the containment check.
    """
    base = base_dir.resolve()
    candidate = base.joinpath(*parts).resolve()
    if not candidate.is_relative_to(base):
        raise UnsafePathError(f"Path {candidate} escapes {base}")
    return candidate
