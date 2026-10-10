from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Double,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import MeasurementStatus, MeasurementType
from app.db.models.types import pg_enum

if TYPE_CHECKING:
    from app.db.models.file import File


class FeatureMeasurement(Base):
    """One feature of an uploaded dataset with its geometry and measurement.

    Geometry is stored twice on purpose:

    * ``geometry_geojson`` - the feature exactly as read, in the *source* CRS
      (``source_crs``), so nothing about the original coordinates is lost;
    * ``display_geometry_geojson`` - the same geometry in EPSG:4326 for map
      rendering (RFC 7946). NULL when the source CRS is unknown.

    Indexing: the unique ``(file_id, feature_index)`` B-tree serves both "all
    features of a file" and "feature N of a file, in order" lookups, so separate
    single-column indexes on ``file_id`` / ``feature_index`` would be redundant.
    """

    __tablename__ = "feature_measurements"
    __table_args__ = (
        UniqueConstraint("file_id", "feature_index"),
        CheckConstraint("feature_index >= 0", name="feature_index_non_negative"),
        CheckConstraint(
            "(measurement_status = 'COMPLETED') = (measurement_value IS NOT NULL)",
            name="value_present_iff_completed",
        ),
        CheckConstraint(
            "measurement_value IS NULL OR measurement_value >= 0",
            name="measurement_value_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    file_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("files.id", ondelete="CASCADE"))
    feature_index: Mapped[int] = mapped_column(
        Integer, comment="Zero-based position in the dataset; deterministic per upload."
    )
    source_feature_id: Mapped[str | None] = mapped_column(
        String(255), comment="Identifier from the source (Shapefile FID, KML Placemark id)."
    )
    source_layer: Mapped[str | None] = mapped_column(
        String(255), comment="Source layer (KML folder / Shapefile name)."
    )
    geometry_type: Mapped[str | None] = mapped_column(
        String(32), comment="OGC type name, e.g. Polygon; NULL for a null geometry."
    )
    geometry_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    display_geometry_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    geometry_valid: Mapped[bool | None] = mapped_column(
        Boolean, comment="OGC validity of the source geometry; NULL when not evaluated."
    )
    geometry_repaired: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    source_crs: Mapped[str | None] = mapped_column(Text)
    measurement_crs: Mapped[str | None] = mapped_column(Text)
    measurement_type: Mapped[MeasurementType | None] = mapped_column(
        pg_enum(MeasurementType, "measurement_type")
    )
    measurement_value: Mapped[float | None] = mapped_column(
        Double, comment="Full-precision SI value: square metres or metres."
    )
    measurement_unit: Mapped[str | None] = mapped_column(String(32))
    measurement_status: Mapped[MeasurementStatus] = mapped_column(
        pg_enum(MeasurementStatus, "measurement_status")
    )
    measurement_error: Mapped[str | None] = mapped_column(Text)

    file: Mapped[File] = relationship(back_populates="features")

    def __repr__(self) -> str:
        return (
            f"FeatureMeasurement(file_id={self.file_id}, index={self.feature_index}, "
            f"type={self.geometry_type}, status={self.measurement_status})"
        )
