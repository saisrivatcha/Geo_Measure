"""Persistence and aggregation for ``feature_measurements`` rows."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import batched
from typing import Any

from sqlalchemy import Row, func, insert, select
from sqlalchemy.orm import Session

from app.db.models import FeatureMeasurement, MeasurementStatus, MeasurementType

POLYGON_TYPES = ("Polygon", "MultiPolygon")
LINE_TYPES = ("LineString", "MultiLineString", "LinearRing")
POINT_TYPES = ("Point", "MultiPoint")


@dataclass(frozen=True, slots=True)
class MeasurementAggregates:
    total: int
    by_status: dict[MeasurementStatus, int]
    polygon_count: int
    line_count: int
    measured_polygon_count: int
    measured_line_count: int
    point_count: int
    other_count: int
    total_area_square_meters: float
    total_length_meters: float


class FeatureMeasurementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def bulk_insert(self, rows: Iterable[dict[str, Any]], *, batch_size: int = 1000) -> int:
        """Insert rows in batches of multi-row INSERTs; returns the row count.

        Batching bounds the memory used to build parameters for very large
        datasets. It does not commit: every batch belongs to the caller's
        transaction, so a failure in any batch rolls back all of them.
        """
        inserted = 0
        for batch in batched(rows, batch_size):
            self.session.execute(insert(FeatureMeasurement), list(batch))
            inserted += len(batch)
        return inserted

    def page(self, file_id: uuid.UUID, *, limit: int, offset: int) -> Sequence[FeatureMeasurement]:
        return self.session.scalars(
            select(FeatureMeasurement)
            .where(FeatureMeasurement.file_id == file_id)
            .order_by(FeatureMeasurement.feature_index)
            .limit(limit)
            .offset(offset)
        ).all()

    def display_features(self, file_id: uuid.UUID, *, limit: int) -> Sequence[Row[Any]]:
        """Only the columns a map preview needs, in feature order."""
        return self.session.execute(
            select(
                FeatureMeasurement.feature_index,
                FeatureMeasurement.source_feature_id,
                FeatureMeasurement.geometry_type,
                FeatureMeasurement.display_geometry_geojson,
                FeatureMeasurement.properties,
                FeatureMeasurement.measurement_type,
                FeatureMeasurement.measurement_value,
                FeatureMeasurement.measurement_unit,
                FeatureMeasurement.measurement_status,
            )
            .where(FeatureMeasurement.file_id == file_id)
            .order_by(FeatureMeasurement.feature_index)
            .limit(limit)
        ).all()

    def get(self, file_id: uuid.UUID, feature_index: int) -> FeatureMeasurement | None:
        return self.session.scalars(
            select(FeatureMeasurement).where(
                FeatureMeasurement.file_id == file_id,
                FeatureMeasurement.feature_index == feature_index,
            )
        ).one_or_none()

    def aggregates(self, file_id: uuid.UUID | None = None) -> MeasurementAggregates:
        """All summary figures in one query, for one file or (``None``) every file."""
        fm = FeatureMeasurement
        status_counts = [
            func.count().filter(fm.measurement_status == status).label(status.value)
            for status in MeasurementStatus
        ]
        row = self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(fm.geometry_type.in_(POLYGON_TYPES)).label("polygons"),
                func.count().filter(fm.geometry_type.in_(LINE_TYPES)).label("lines"),
                func.count().filter(fm.geometry_type.in_(POINT_TYPES)).label("points"),
                func.count()
                .filter(
                    fm.geometry_type.is_not(None),
                    fm.geometry_type.not_in(POLYGON_TYPES + LINE_TYPES + POINT_TYPES),
                )
                .label("others"),
                func.count()
                .filter(fm.measurement_type == MeasurementType.AREA)
                .label("measured_polygons"),
                func.count()
                .filter(fm.measurement_type == MeasurementType.LENGTH)
                .label("measured_lines"),
                func.coalesce(
                    func.sum(fm.measurement_value).filter(
                        fm.measurement_type == MeasurementType.AREA
                    ),
                    0.0,
                ).label("area"),
                func.coalesce(
                    func.sum(fm.measurement_value).filter(
                        fm.measurement_type == MeasurementType.LENGTH
                    ),
                    0.0,
                ).label("length"),
                *status_counts,
            ).where(*([fm.file_id == file_id] if file_id is not None else []))
        ).one()
        mapping = row._mapping
        return MeasurementAggregates(
            total=row.total,
            by_status={status: mapping[status.value] for status in MeasurementStatus},
            polygon_count=row.polygons,
            line_count=row.lines,
            measured_polygon_count=row.measured_polygons,
            measured_line_count=row.measured_lines,
            point_count=row.points,
            other_count=row.others,
            total_area_square_meters=float(row.area),
            total_length_meters=float(row.length),
        )
