"""Read side of measurements: summaries, paginated feature results, map previews."""

from __future__ import annotations

import math
import uuid

from app.db.models import FeatureMeasurement, File, FileStatus, MeasurementStatus, MeasurementType
from app.exceptions import FeatureNotFoundError, FileNotProcessedError, FileRecordNotFoundError
from app.geospatial.crs import DISPLAY_CRS_LABEL
from app.repositories.feature_measurement_repository import FeatureMeasurementRepository
from app.repositories.file_repository import FileRepository
from app.schemas.geojson import (
    FeatureCollection,
    FeatureMeasurementSummary,
    GeoJSONFeature,
    PreviewMetadata,
)
from app.schemas.measurements import (
    FeatureDetail,
    FeatureMeasurementRead,
    Measurement,
    MeasurementsPage,
    MeasurementSummary,
)
from app.schemas.system import FileCounts, WorkspaceStats

SQUARE_METERS_PER_HECTARE = 10_000.0
SQUARE_METERS_PER_SQUARE_KM = 1_000_000.0
METERS_PER_KM = 1_000.0


class MeasurementService:
    def __init__(
        self,
        files: FileRepository,
        features: FeatureMeasurementRepository,
        *,
        preview_max_features: int,
    ) -> None:
        self.files = files
        self.features = features
        self.preview_max_features = preview_max_features

    def summary(self, file_id: uuid.UUID | None) -> MeasurementSummary:
        """Summary for one file, or for every file when ``file_id`` is ``None``."""
        aggregates = self.features.aggregates(file_id)
        counts = aggregates.by_status
        return MeasurementSummary(
            total_features=aggregates.total,
            measured_features=counts[MeasurementStatus.COMPLETED],
            not_required_features=counts[MeasurementStatus.NOT_REQUIRED],
            unsupported_features=counts[MeasurementStatus.NOT_SUPPORTED],
            invalid_features=counts[MeasurementStatus.INVALID_GEOMETRY],
            no_geometry_features=counts[MeasurementStatus.NO_GEOMETRY],
            crs_unavailable_features=counts[MeasurementStatus.CRS_UNAVAILABLE],
            failed_features=counts[MeasurementStatus.FAILED],
            polygon_count=aggregates.polygon_count,
            line_count=aggregates.line_count,
            measured_polygon_count=aggregates.measured_polygon_count,
            measured_line_count=aggregates.measured_line_count,
            point_count=aggregates.point_count,
            other_count=aggregates.other_count,
            total_area_square_meters=aggregates.total_area_square_meters,
            total_length_meters=aggregates.total_length_meters,
        )

    def measurements_page(
        self, file_id: uuid.UUID, *, page: int, page_size: int
    ) -> MeasurementsPage:
        file = self._completed_file(file_id)
        summary = self.summary(file_id)
        rows = self.features.page(file_id, limit=page_size, offset=(page - 1) * page_size)
        return MeasurementsPage(
            file_id=file.id,
            source_crs=file.source_crs,
            measurement_crs=file.measurement_crs,
            summary=summary,
            page=page,
            page_size=page_size,
            total=summary.total_features,
            total_pages=math.ceil(summary.total_features / page_size),
            features=[to_feature_read(row) for row in rows],
        )

    def geojson_preview(self, file_id: uuid.UUID, *, limit: int | None = None) -> FeatureCollection:
        """EPSG:4326 FeatureCollection, capped at ``preview_max_features``."""
        file = self._completed_file(file_id)
        cap = min(limit or self.preview_max_features, self.preview_max_features)
        rows = self.features.display_features(file_id, limit=cap)
        total = file.feature_count or 0
        features = [
            GeoJSONFeature(
                id=row.feature_index,
                geometry=row.display_geometry_geojson,
                properties=row.properties,
                geomeasure=FeatureMeasurementSummary(
                    feature_index=row.feature_index,
                    geometry_type=row.geometry_type,
                    measurement_status=row.measurement_status,
                    measurement_type=row.measurement_type,
                    measurement_value=row.measurement_value,
                    measurement_unit=row.measurement_unit,
                ),
            )
            for row in rows
        ]
        return FeatureCollection(
            features=features,
            metadata=PreviewMetadata(
                total_features=total,
                returned_features=len(features),
                truncated=len(features) < total,
                display_crs=DISPLAY_CRS_LABEL,
                source_crs=file.source_crs,
                measurement_crs=file.measurement_crs,
                features_without_geometry=sum(1 for f in features if f.geometry is None),
            ),
        )

    def feature_detail(self, file_id: uuid.UUID, feature_index: int) -> FeatureDetail:
        self._completed_file(file_id)
        row = self.features.get(file_id, feature_index)
        if row is None:
            raise FeatureNotFoundError(
                details={"file_id": str(file_id), "feature_index": feature_index}
            )
        return FeatureDetail(
            **to_feature_read(row).model_dump(),
            display_geometry=row.display_geometry_geojson,
            geometry=row.geometry_geojson,
        )

    def workspace_stats(self) -> WorkspaceStats:
        counts = self.files.count_by_status()
        return WorkspaceStats(
            files=FileCounts(
                total=sum(counts.values()),
                completed=counts[FileStatus.COMPLETED],
                in_progress=counts[FileStatus.PENDING] + counts[FileStatus.PROCESSING],
                failed=counts[FileStatus.FAILED],
            ),
            features=self.summary(None),
        )

    def _completed_file(self, file_id: uuid.UUID) -> File:
        file = self.files.get(file_id)
        if file is None:
            raise FileRecordNotFoundError(details={"file_id": str(file_id)})
        if file.status is not FileStatus.COMPLETED:
            raise FileNotProcessedError(
                f"The file is {file.status.value}; results are only available once COMPLETED.",
                details={
                    "file_id": str(file_id),
                    "status": file.status.value,
                    "processing_error": file.processing_error,
                },
            )
        return file


def to_feature_read(row: FeatureMeasurement) -> FeatureMeasurementRead:
    return FeatureMeasurementRead(
        feature_index=row.feature_index,
        source_feature_id=row.source_feature_id,
        source_layer=row.source_layer,
        geometry_type=row.geometry_type,
        geometry_valid=row.geometry_valid,
        geometry_repaired=row.geometry_repaired,
        measurement=to_measurement(
            row.measurement_type, row.measurement_value, row.measurement_unit
        ),
        measurement_status=row.measurement_status,
        measurement_error=row.measurement_error,
        source_crs=row.source_crs,
        measurement_crs=row.measurement_crs,
        properties=row.properties,
    )


def to_measurement(
    measurement_type: MeasurementType | None, value: float | None, unit: str | None
) -> Measurement | None:
    """Raw SI value plus derived units; the raw value is never rounded."""
    if measurement_type is None or value is None or unit is None:
        return None
    if measurement_type is MeasurementType.AREA:
        return Measurement(
            type=measurement_type,
            value=value,
            unit=unit,
            area_square_km=value / SQUARE_METERS_PER_SQUARE_KM,
            area_hectares=value / SQUARE_METERS_PER_HECTARE,
            display=format_area(value),
        )
    return Measurement(
        type=measurement_type,
        value=value,
        unit=unit,
        length_km=value / METERS_PER_KM,
        display=format_length(value),
    )


def format_area(square_meters: float) -> str:
    if square_meters < SQUARE_METERS_PER_HECTARE:
        return f"{square_meters:,.2f} m²"
    if square_meters < SQUARE_METERS_PER_SQUARE_KM:
        return f"{square_meters / SQUARE_METERS_PER_HECTARE:,.2f} ha"
    return f"{square_meters / SQUARE_METERS_PER_SQUARE_KM:,.3f} km²"


def format_length(meters: float) -> str:
    if meters < METERS_PER_KM:
        return f"{meters:,.2f} m"
    return f"{meters / METERS_PER_KM:,.3f} km"
