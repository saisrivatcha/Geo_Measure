"""Public representations of uploaded files.

``stored_path`` is deliberately not exposed: storage layout is an internal detail.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.db.models import FileStatus, FileType
from app.geospatial.crs import describe_crs
from app.schemas import examples
from app.schemas.measurements import MeasurementSummary


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [examples.FILE]})

    id: uuid.UUID
    filename: str = Field(description="Sanitised original filename.")
    file_type: FileType
    status: FileStatus
    file_size_bytes: int
    feature_count: int | None = Field(description="Number of features; null until processed.")
    source_crs: str | None = Field(
        description="CRS of the source data (e.g. EPSG:4326); null when the dataset has none.",
        examples=["EPSG:4326"],
    )
    source_crs_assumed: bool = Field(
        description="True when source_crs was not in the file but implied by the format "
        "(a KML without a CRS is WGS 84 by specification)."
    )
    measurement_crs: str | None = Field(
        description="Projected CRS used for area/length; null when nothing was measured.",
        examples=["EPSG:32644"],
    )
    processing_error: str | None = Field(description="User-safe failure reason when FAILED.")

    @computed_field(  # type: ignore[prop-decorator]
        description="Human-readable name of source_crs, e.g. 'WGS 84'.",
        examples=["WGS 84"],
    )
    @property
    def source_crs_name(self) -> str | None:
        return describe_crs(self.source_crs)

    @computed_field(  # type: ignore[prop-decorator]
        description="Human-readable name of measurement_crs, e.g. 'WGS 84 / UTM zone 44N'.",
        examples=["WGS 84 / UTM zone 44N"],
    )
    @property
    def measurement_crs_name(self) -> str | None:
        return describe_crs(self.measurement_crs)

    created_at: datetime
    completed_at: datetime | None = Field(description="When processing finished (either outcome).")


class FileList(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"items": [examples.FILE], "page": 1, "page_size": 20, "total": 1, "total_pages": 1}
            ]
        }
    )

    items: list[FileRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class FileLinks(BaseModel):
    self: str
    measurements: str
    geojson: str


class FileProcessingResult(BaseModel):
    """Returned by the upload endpoint once processing has finished."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file": examples.FILE,
                    "summary": examples.SUMMARY,
                    "links": {
                        "self": f"/api/files/{examples.FILE_ID}/",
                        "measurements": f"/api/files/{examples.FILE_ID}/measurements/",
                        "geojson": f"/api/files/{examples.FILE_ID}/geojson",
                    },
                }
            ]
        }
    )

    file: FileRead
    summary: MeasurementSummary
    links: FileLinks
