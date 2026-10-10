"""Workspace-wide statistics and public configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.measurements import MeasurementSummary


class FileCounts(BaseModel):
    total: int
    completed: int
    in_progress: int = Field(description="PENDING or PROCESSING.")
    failed: int


class WorkspaceStats(BaseModel):
    files: FileCounts
    features: MeasurementSummary = Field(description="Across all completed files.")


class UploadLimits(BaseModel):
    max_upload_size_mb: int
    max_upload_bytes: int
    allowed_extensions: list[str]


class MeasurementSettings(BaseModel):
    area_unit: str = "square_meters"
    length_unit: str = "meters"
    max_linear_distortion: float = Field(
        description="Largest scale error accepted for a measurement CRS (0.001 = 0.1 %)."
    )
    crs_strategy: list[str] = Field(description="Candidate CRSs, tried in order.")


class ServiceInfo(BaseModel):
    name: str
    version: str
    environment: str
    upload: UploadLimits
    measurement: MeasurementSettings
    geojson_preview_max_features: int
