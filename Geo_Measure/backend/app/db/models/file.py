from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import FileStatus, FileType
from app.db.models.types import pg_enum

if TYPE_CHECKING:
    from app.db.models.feature_measurement import FeatureMeasurement


class File(Base):
    """An uploaded dataset. The binary lives on disk under ``stored_path``."""

    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint("file_size_bytes >= 0", name="file_size_non_negative"),
        CheckConstraint(
            "feature_count IS NULL OR feature_count >= 0", name="feature_count_non_negative"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[FileType] = mapped_column(pg_enum(FileType, "file_type"))
    stored_path: Mapped[str] = mapped_column(
        String(1024), comment="Path of the original upload, relative to STORAGE_DIR."
    )
    status: Mapped[FileStatus] = mapped_column(
        pg_enum(FileStatus, "file_status"),
        default=FileStatus.PENDING,
        server_default=FileStatus.PENDING.value,
        index=True,
    )
    feature_count: Mapped[int | None] = mapped_column(Integer)
    source_crs: Mapped[str | None] = mapped_column(
        Text, comment="CRS of the source data, e.g. EPSG:4326; NULL when unknown."
    )
    source_crs_assumed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        comment="True when source_crs comes from format rules (KML = WGS 84), not the file.",
    )
    measurement_crs: Mapped[str | None] = mapped_column(
        Text, comment="Projected CRS used for measurements; NULL if nothing was measured."
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    features: Mapped[list[FeatureMeasurement]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FeatureMeasurement.feature_index",
    )

    def __repr__(self) -> str:
        return f"File(id={self.id}, filename={self.filename!r}, status={self.status})"
