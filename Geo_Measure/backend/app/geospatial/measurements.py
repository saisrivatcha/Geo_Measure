"""Feature-level area and length measurement.

All heavy work is vectorised over the whole dataset with Shapely 2 / GeoPandas:
one type classification, one validity pass, a single CRS transformation (one
PROJ transformer for the whole frame) and one ``area``/``length`` call.
Python-level loops only touch invalid geometries (repair) and the final
per-feature result objects.

Units: values are always SI - square metres for areas, metres for lengths -
at full float precision. If the measurement CRS uses another linear unit (e.g.
US survey feet) the projected values are converted. Measurement is planimetric:
any Z coordinate is ignored.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import shapely
from pyproj import CRS

from app.db.models.enums import MeasurementStatus, MeasurementType, MeasurementUnit
from app.geospatial.crs import is_measurable_crs, select_measurement_crs
from app.geospatial.models import (
    FeatureMeasurementResult,
    GeometryFamily,
    MeasurementCRS,
)
from app.geospatial.validators import validate_and_repair

logger = logging.getLogger(__name__)

# Shapely type ids
_FAMILIES: dict[int, GeometryFamily] = {
    0: GeometryFamily.PUNTAL,  # Point
    1: GeometryFamily.LINEAR,  # LineString
    2: GeometryFamily.LINEAR,  # LinearRing
    3: GeometryFamily.POLYGONAL,  # Polygon
    4: GeometryFamily.PUNTAL,  # MultiPoint
    5: GeometryFamily.LINEAR,  # MultiLineString
    6: GeometryFamily.POLYGONAL,  # MultiPolygon
    7: GeometryFamily.COLLECTION,  # GeometryCollection
}

MESSAGE_CRS_UNAVAILABLE = (
    "The dataset has no coordinate reference system, so metric measurements cannot be computed."
)
MESSAGE_CRS_NOT_MEASURABLE = (
    "The coordinate reference system is neither geographic nor projected; "
    "measurements cannot be computed."
)
MESSAGE_OUT_OF_RANGE = (
    "Coordinates fall outside the valid longitude/latitude range of the declared CRS; "
    "the dataset's CRS is probably wrong."
)
MESSAGE_TRANSFORM_FAILED = "The geometry could not be transformed into the measurement CRS."
MESSAGE_GEOMETRY_COLLECTION = "Geometry collections are not measured."


@dataclass(frozen=True, slots=True)
class MeasurementOutcome:
    """Per-feature results (aligned with the input rows) and the CRS that produced them."""

    results: list[FeatureMeasurementResult]
    measurement_crs: MeasurementCRS | None


@dataclass(slots=True)
class _Columns:
    """Per-feature result columns, filled in stages."""

    statuses: np.ndarray
    errors: np.ndarray
    values: np.ndarray
    valid: np.ndarray
    repaired: np.ndarray

    @classmethod
    def initial(cls, families: np.ndarray) -> _Columns:
        size = len(families)
        statuses = np.full(size, MeasurementStatus.NOT_SUPPORTED, dtype=object)
        statuses[families == GeometryFamily.PUNTAL] = MeasurementStatus.NOT_REQUIRED
        statuses[families == GeometryFamily.EMPTY] = MeasurementStatus.NO_GEOMETRY
        errors = np.full(size, None, dtype=object)
        errors[families == GeometryFamily.COLLECTION] = MESSAGE_GEOMETRY_COLLECTION
        return cls(
            statuses=statuses,
            errors=errors,
            values=np.full(size, np.nan),
            valid=np.full(size, None, dtype=object),
            repaired=np.zeros(size, dtype=bool),
        )

    def mark(self, mask: np.ndarray, status: MeasurementStatus, error: object) -> None:
        self.statuses[mask] = status
        self.errors[mask] = error


class MeasurementEngine:
    """Measures every feature of a GeoDataFrame in an automatically chosen metric CRS."""

    def measure(self, frame: gpd.GeoDataFrame) -> MeasurementOutcome:
        geometries = frame.geometry.to_numpy()
        families = classify(geometries)
        polygonal = families == GeometryFamily.POLYGONAL
        measurable = polygonal | (families == GeometryFamily.LINEAR)
        columns = _Columns.initial(families)

        to_measure = np.full(len(geometries), None, dtype=object)
        if measurable.any():
            check = validate_and_repair(geometries[measurable], families[measurable].astype(str))
            columns.valid[measurable] = check.valid
            columns.repaired[measurable] = check.repaired
            to_measure[measurable] = check.measurable

            unrepairable = np.zeros(len(geometries), dtype=bool)
            unrepairable[measurable] = check.unrepairable
            columns.mark(
                unrepairable,
                MeasurementStatus.INVALID_GEOMETRY,
                [
                    f"Invalid geometry that could not be repaired: {reason}"
                    for reason in check.reasons[check.unrepairable]
                ],
            )
            measurable &= ~unrepairable

        measurement_crs = self._measure(frame.crs, to_measure, measurable, polygonal, columns)
        results = [
            _result(
                columns.statuses[i],
                bool(polygonal[i]),
                columns.values[i],
                columns.errors[i],
                columns.valid[i],
                bool(columns.repaired[i]),
            )
            for i in range(len(geometries))
        ]
        _log_summary(columns.statuses, measurement_crs)
        return MeasurementOutcome(results, measurement_crs)

    def _measure(
        self,
        source: CRS | None,
        to_measure: np.ndarray,
        measurable: np.ndarray,
        polygonal: np.ndarray,
        columns: _Columns,
    ) -> MeasurementCRS | None:
        """Fill values for ``measurable`` rows; returns the measurement CRS used."""
        if not measurable.any():
            return None
        if source is None or not is_measurable_crs(source):
            message = MESSAGE_CRS_UNAVAILABLE if source is None else MESSAGE_CRS_NOT_MEASURABLE
            columns.mark(measurable, MeasurementStatus.CRS_UNAVAILABLE, message)
            return None

        bounds = shapely.bounds(to_measure)
        if source.is_geographic:
            out_of_range = measurable & ~_within_lonlat_range(bounds)
            columns.mark(out_of_range, MeasurementStatus.FAILED, MESSAGE_OUT_OF_RANGE)
            measurable = measurable & ~out_of_range

        measurement_crs = select_measurement_crs(source, bounds[measurable])
        if measurement_crs is None:
            columns.mark(measurable, MeasurementStatus.FAILED, MESSAGE_TRANSFORM_FAILED)
            return None

        # One vectorised transformation for every measurable feature.
        projected = (
            gpd.GeoSeries(to_measure[measurable], crs=source).to_crs(measurement_crs.crs).to_numpy()
        )
        scale = measurement_crs.metres_per_unit
        raw = np.where(
            polygonal[measurable],
            shapely.area(projected) * scale * scale,
            shapely.length(projected) * scale,
        )

        finite = np.isfinite(raw)
        indices = np.flatnonzero(measurable)
        columns.values[indices[finite]] = raw[finite]
        columns.statuses[indices[finite]] = MeasurementStatus.COMPLETED
        columns.mark(indices[~finite], MeasurementStatus.FAILED, MESSAGE_TRANSFORM_FAILED)
        return measurement_crs


def classify(geometries: np.ndarray) -> np.ndarray:
    """Geometry family per row; null and empty geometries are ``EMPTY``."""
    type_ids = shapely.get_type_id(geometries)
    empty = (type_ids < 0) | shapely.is_empty(geometries)
    families = np.array(
        [_FAMILIES.get(int(type_id), GeometryFamily.UNKNOWN) for type_id in type_ids], dtype=object
    )
    families[empty] = GeometryFamily.EMPTY
    return families


def _within_lonlat_range(bounds: np.ndarray) -> np.ndarray:
    """Longitudes in [-180, 360] (0-360 conventions are legal), latitudes in [-90, 90]."""
    minx, miny, maxx, maxy = bounds.T
    with np.errstate(invalid="ignore"):
        return (minx >= -180) & (maxx <= 360) & (miny >= -90) & (maxy <= 90)


def _result(
    status: str,
    is_polygon: bool,
    value: float,
    error: str | None,
    valid: bool | None,
    repaired: bool,
) -> FeatureMeasurementResult:
    # numpy object arrays may hold the enum's plain-str value; normalise.
    status = MeasurementStatus(status)
    if status is MeasurementStatus.COMPLETED:
        measurement_type = MeasurementType.AREA if is_polygon else MeasurementType.LENGTH
        unit = MeasurementUnit.SQUARE_METERS if is_polygon else MeasurementUnit.METERS
        return FeatureMeasurementResult(
            status=status,
            measurement_type=measurement_type,
            value=float(value),
            unit=unit,
            geometry_valid=None if valid is None else bool(valid),
            geometry_repaired=repaired,
        )
    return FeatureMeasurementResult(
        status=status,
        error=error,
        geometry_valid=None if valid is None else bool(valid),
        geometry_repaired=repaired,
    )


def _log_summary(statuses: np.ndarray, measurement_crs: MeasurementCRS | None) -> None:
    labels, counts = np.unique(statuses.astype(str), return_counts=True)
    logger.info(
        "measurement.completed",
        extra={
            "measurement_crs": measurement_crs.label if measurement_crs else None,
            "statuses": dict(zip(labels.tolist(), counts.tolist(), strict=True)),
        },
    )
