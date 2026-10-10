"""Per-feature measurement responses and the per-file summary."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import MeasurementStatus, MeasurementType
from app.schemas import examples


class Measurement(BaseModel):
    type: MeasurementType
    value: float = Field(
        description="Full-precision SI value: square_meters for AREA, meters for LENGTH."
    )
    unit: str = Field(examples=["square_meters", "meters"])
    area_square_km: float | None = Field(default=None, description="AREA only.")
    area_hectares: float | None = Field(default=None, description="AREA only.")
    length_km: float | None = Field(default=None, description="LENGTH only.")
    display: str = Field(description="Rounded, human-readable value.", examples=["1.18 km²"])


class FeatureMeasurementRead(BaseModel):
    feature_index: int = Field(description="Zero-based, deterministic position in the dataset.")
    source_feature_id: str | None = Field(
        description="Identifier from the source: Shapefile record number or KML Placemark id."
    )
    source_layer: str | None = Field(description="KML folder or Shapefile layer name.")
    geometry_type: str | None = Field(examples=["Polygon"])
    geometry_valid: bool | None = Field(
        description="OGC validity of the source geometry (null for types not checked)."
    )
    geometry_repaired: bool = Field(
        description="True when an invalid geometry was repaired before measuring. "
        "The stored geometry remains the original."
    )
    measurement: Measurement | None
    measurement_status: MeasurementStatus
    measurement_error: str | None
    source_crs: str | None
    measurement_crs: str | None
    properties: dict[str, Any]


class MeasurementSummary(BaseModel):
    total_features: int
    measured_features: int = Field(description="Features with a COMPLETED measurement.")
    not_required_features: int = Field(description="Points: nothing to measure.")
    unsupported_features: int = Field(description="Geometry collections / unknown types.")
    invalid_features: int = Field(description="Invalid and not safely repairable.")
    no_geometry_features: int
    crs_unavailable_features: int
    failed_features: int
    polygon_count: int
    line_count: int
    measured_polygon_count: int = Field(description="Polygons with a COMPLETED area.")
    measured_line_count: int = Field(description="Lines with a COMPLETED length.")
    point_count: int
    other_count: int = Field(
        description="Features of other types (e.g. GeometryCollection); null geometries excluded."
    )
    total_area_square_meters: float
    total_length_meters: float


class MeasurementsPage(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_id": examples.FILE_ID,
                    "source_crs": "EPSG:4326",
                    "measurement_crs": "EPSG:32644",
                    "summary": examples.SUMMARY,
                    "page": 1,
                    "page_size": 50,
                    "total": 27,
                    "total_pages": 1,
                    "features": [examples.FEATURE, examples.POINT_FEATURE],
                }
            ]
        }
    )

    file_id: uuid.UUID
    source_crs: str | None
    measurement_crs: str | None
    summary: MeasurementSummary
    page: int
    page_size: int
    total: int
    total_pages: int
    features: list[FeatureMeasurementRead]


class FeatureDetail(FeatureMeasurementRead):
    """One feature including its geometry, for detail views and map highlighting."""

    display_geometry: dict[str, Any] | None = Field(
        description="EPSG:4326 GeoJSON geometry; null when the CRS is unknown."
    )
    geometry: dict[str, Any] | None = Field(description="GeoJSON geometry in source_crs.")
