"""Plain data structures exchanged inside the geospatial package.

These are not ORM models: the package never touches the database. The service
layer maps :class:`ProcessedFeature` onto ``FeatureMeasurement`` rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pyproj import CRS

from app.db.models.enums import MeasurementStatus, MeasurementType, MeasurementUnit

# Columns that readers add to the GeoDataFrame next to ``geometry``. Source
# attributes are folded into PROPERTIES_COLUMN (one dict per row) so a
# multi-layer KML keeps each layer's own schema and attribute names can never
# collide with these reserved names.
SOURCE_LAYER_COLUMN = "__source_layer"
SOURCE_FEATURE_ID_COLUMN = "__source_feature_id"
PROPERTIES_COLUMN = "__properties"


class GeometryFamily(StrEnum):
    POLYGONAL = "polygonal"
    LINEAR = "linear"
    PUNTAL = "puntal"
    COLLECTION = "collection"
    EMPTY = "empty"
    UNKNOWN = "unknown"


class CRSStrategy(StrEnum):
    """How the measurement CRS was chosen (logged and kept for diagnostics)."""

    SOURCE_PROJECTED = "source_projected"
    UTM_ZONE = "utm_zone"
    LOCAL_TRANSVERSE_MERCATOR = "local_transverse_mercator"
    LOCAL_EQUAL_AREA = "local_equal_area"


@dataclass(frozen=True, slots=True)
class SourceCRS:
    crs: CRS | None
    label: str | None
    assumed: bool = False


@dataclass(frozen=True, slots=True)
class MeasurementCRS:
    crs: CRS
    label: str
    strategy: CRSStrategy
    # Multiply projected lengths by this to get metres (1.0 for metre-based CRSs,
    # 0.3048006... for US survey feet). Areas use the square of it.
    metres_per_unit: float
    max_linear_distortion: float


@dataclass(frozen=True, slots=True)
class FeatureMeasurementResult:
    status: MeasurementStatus
    measurement_type: MeasurementType | None = None
    value: float | None = None
    unit: MeasurementUnit | None = None
    error: str | None = None
    geometry_valid: bool | None = None
    geometry_repaired: bool = False


@dataclass(frozen=True, slots=True)
class ProcessedFeature:
    feature_index: int
    source_feature_id: str | None
    source_layer: str | None
    geometry_type: str | None
    geometry: dict[str, Any] | None
    display_geometry: dict[str, Any] | None
    properties: dict[str, Any]
    measurement: FeatureMeasurementResult


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    source_crs: SourceCRS
    measurement_crs: MeasurementCRS | None
    features: list[ProcessedFeature]

    @property
    def feature_count(self) -> int:
        return len(self.features)
