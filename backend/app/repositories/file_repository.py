"""Persistence for ``files`` rows. Repositories never commit; services own transactions."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import File, FileStatus, FileType


class FileSortField(StrEnum):
    CREATED_AT = "created_at"
    FILENAME = "filename"
    FILE_SIZE_BYTES = "file_size_bytes"
    FEATURE_COUNT = "feature_count"
    STATUS = "status"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


_SORT_COLUMNS = {
    FileSortField.CREATED_AT: File.created_at,
    FileSortField.FILENAME: File.filename,
    FileSortField.FILE_SIZE_BYTES: File.file_size_bytes,
    FileSortField.FEATURE_COUNT: File.feature_count,
    FileSortField.STATUS: File.status,
}


class FileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, file: File) -> File:
        self.session.add(file)
        self.session.flush()
        return file

    def get(self, file_id: uuid.UUID) -> File | None:
        return self.session.get(File, file_id)

    def list(
        self,
        *,
        limit: int,
        offset: int,
        sort: FileSortField = FileSortField.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        status: FileStatus | None = None,
        file_type: FileType | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[File], int]:
        """A page of files plus the total matching count.

        ``id`` is a tiebreaker so pages are stable when sort values repeat.
        """
        filters = []
        if status:
            filters.append(File.status == status)
        if file_type:
            filters.append(File.file_type == file_type)
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(File.filename.ilike(f"%{escaped}%", escape="\\"))
        column = _SORT_COLUMNS[sort]
        ordering = (
            (column.asc().nulls_first(), File.id.asc())
            if order is SortOrder.ASC
            else (column.desc().nulls_last(), File.id.desc())
        )
        total = self.session.scalar(select(func.count()).select_from(File).where(*filters)) or 0
        rows = self.session.scalars(
            select(File).where(*filters).order_by(*ordering).limit(limit).offset(offset)
        ).all()
        return rows, total

    def count_by_status(self) -> dict[FileStatus, int]:
        rows = self.session.execute(select(File.status, func.count()).group_by(File.status)).all()
        counts = dict.fromkeys(FileStatus, 0)
        counts.update(dict(rows))
        return counts
