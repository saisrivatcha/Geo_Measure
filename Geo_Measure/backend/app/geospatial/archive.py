"""Safe extraction of a validated Shapefile bundle.

Only the members of the selected :class:`ShapefileBundle` are extracted; any
other archive content is ignored. Members are written flat into the destination
under a sanitised common stem so GDAL can locate the sidecar files, and each is
created with exclusive mode so nothing can be overwritten.
"""

from __future__ import annotations

import logging
import zipfile
from collections.abc import Iterable
from pathlib import Path

from app.core.security import UnsafePathError, resolve_within, sanitize_filename
from app.exceptions import InvalidArchiveError, UnsafeArchiveError
from app.geospatial.validators import ShapefileBundle

logger = logging.getLogger(__name__)

_COPY_CHUNK_BYTES = 1024 * 1024


def extract_shapefile_bundle(
    archive_path: Path,
    bundle: ShapefileBundle,
    destination: Path,
    *,
    max_extracted_bytes: int,
) -> dict[str, Path]:
    """Extract ``bundle`` into ``destination`` and return ``{extension: path}``.

    The byte budget is enforced on the bytes actually decompressed, not on the
    sizes declared in the central directory, which an attacker controls.
    On any failure every file written so far is removed.
    """
    try:
        stem = sanitize_filename(bundle.stem)
    except UnsafePathError as exc:
        raise UnsafeArchiveError(details={"member": bundle.stem}) from exc

    destination.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    budget = _ByteBudget(max_extracted_bytes)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for extension, member_name in sorted(bundle.members.items()):
                target = resolve_within(destination, f"{stem}{extension}")
                _extract_member(archive, member_name, target, budget)
                written[extension] = target
    except (UnsafePathError, FileExistsError) as exc:
        _remove_all(written.values())
        raise UnsafeArchiveError(details={"reason": type(exc).__name__}) from exc
    except (zipfile.BadZipFile, OSError, EOFError) as exc:
        _remove_all(written.values())
        raise InvalidArchiveError("The archive is corrupt and could not be extracted.") from exc
    except InvalidArchiveError:
        _remove_all(written.values())
        raise

    logger.info(
        "upload.archive_extracted",
        extra={"components": sorted(written), "extracted_bytes": budget.used},
    )
    return written


class _ByteBudget:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0

    def consume(self, size: int) -> None:
        self.used += size
        if self.used > self.limit:
            raise UnsafeArchiveError(
                "The archive expands beyond the allowed size.",
                details={"max_extracted_bytes": self.limit},
            )


def _extract_member(
    archive: zipfile.ZipFile, member_name: str, target: Path, budget: _ByteBudget
) -> None:
    # Mode "xb" fails if the target exists: no overwrite, no symlink following.
    with archive.open(member_name) as source, target.open("xb") as sink:
        try:
            while chunk := source.read(_COPY_CHUNK_BYTES):
                budget.consume(len(chunk))
                sink.write(chunk)
        except BaseException:
            sink.close()
            target.unlink(missing_ok=True)
            raise


def _remove_all(paths: Iterable[Path]) -> None:
    for path in list(paths):
        path.unlink(missing_ok=True)
