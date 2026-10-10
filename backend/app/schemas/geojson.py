"""RFC 7946 FeatureCollection for map previews."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import MeasurementStatus, MeasurementType
from app.schemas import examples


class FeatureMeasurementSummary(BaseModel):
    feature_index: int
    geometry_type: str | None
    measurement_status: MeasurementStatus
    measurement_type: MeasurementType | None
    measurement_value: float | None
    measurement_unit: str | None


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: int = Field(description="feature_index")
    geometry: dict[str, Any] | None = Field(
        description="EPSG:4326 geometry; null when the feature has no geometry or the "
        "dataset's CRS is unknown (coordinates cannot be placed on a map)."
    )
    properties: dict[str, Any] = Field(description="Source attributes.")
    geomeasure: FeatureMeasurementSummary = Field(
        description="Measurement for this feature (a GeoJSON foreign member, so it can never "
        "collide with source attribute names)."
    )


class PreviewMetadata(BaseModel):
    total_features: int
    returned_features: int
    truncated: bool
    display_crs: str = "EPSG:4326"
    source_crs: str | None
    measurement_crs: str | None
    features_without_geometry: int = Field(
        description="Returned features whose geometry is null (no geometry or unknown CRS)."
    )


class FeatureCollection(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "FeatureCollection",
                    "features": [examples.GEOJSON_FEATURE],
                    "metadata": {
                        "total_features": 27,
                        "returned_features": 27,
                        "truncated": False,
                        "display_crs": "EPSG:4326",
                        "source_crs": "EPSG:4326",
                        "measurement_crs": "EPSG:32644",
                        "features_without_geometry": 0,
                    },
                }
            ]
        }
    )

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]
    metadata: PreviewMetadata
