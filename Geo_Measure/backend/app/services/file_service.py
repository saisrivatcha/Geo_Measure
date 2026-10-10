"""Upload ingestion and file lookups.

Transaction strategy for an upload (each numbered commit is its own transaction):

1. validate filename/extension/declared size - rejected uploads leave no trace;
2. COMMIT a ``PENDING`` row (the upload now exists and can be inspected);
3. stream the original to disk, COMMIT ``PROCESSING``;
4. process the dataset in memory (no database writes);
5. bulk-insert every feature row **and** set ``COMPLETED`` - one COMMIT.

Any failure in 3-5 rolls the session back - so no feature rows survive - and a
fresh transaction marks the file ``FAILED`` with a user-safe message. The
database can therefore never hold a ``COMPLETED`` file with missing features,
or feature rows for a ``FAILED`` file. The original upload is kept on disk for
diagnostics; extracted archive members are always deleted.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import File, FileStatus, FileType
from app.exceptions import AppError, FileRecordNotFoundError
from app.geospatial.models import ProcessedFeature, ProcessingResult
from app.geospatial.processor import GeospatialProcessor
from app.geospatial.serializers import write_feature_collection
from app.geospatial.validators import FileValidator
from app.repositories.feature_measurement_repository import FeatureMeasurementRepository
from app.repositories.file_repository import FileRepository, FileSortField, SortOrder
from app.services.storage import FileStorage, Readable, StorageLayout

logger = logging.getLogger(__name__)

GENERIC_PROCESSING_ERROR = "An unexpected error occurred while processing the file."


class FileService:
    def __init__(
        self,
        session: Session,
        files: FileRepository,
        features: FeatureMeasurementRepository,
        storage: FileStorage,
        validator: FileValidator,
        processor: GeospatialProcessor,
    ) -> None:
        self.session = session
        self.files = files
        self.features = features
        self.storage = storage
        self.validator = validator
        self.processor = processor

    # ---- queries ---------------------------------------------------------------

    def get_file(self, file_id: uuid.UUID) -> File:
        file = self.files.get(file_id)
        if file is None:
            raise FileRecordNotFoundError(details={"file_id": str(file_id)})
        return file

    def list_files(
        self,
        *,
        page: int,
        page_size: int,
        sort: FileSortField,
        order: SortOrder,
        status: FileStatus | None,
        file_type: FileType | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[File], int]:
        return self.files.list(
            limit=page_size,
            offset=(page - 1) * page_size,
            sort=sort,
            order=order,
            status=status,
            file_type=file_type,
            search=search,
        )

    # ---- upload ----------------------------------------------------------------

    def upload(self, filename: str | None, stream: Readable, declared_size: int | None) -> File:
        """Store and process an upload; returns the ``COMPLETED`` file.

        Raises an :class:`AppError`. When the failure happens after the file
        record exists, the error's ``details`` include ``file_id`` and the
        record is ``FAILED``.
        """
        validated = self.validator.validate_upload(filename, declared_size)
        file_id = uuid.uuid4()
        layout = self.storage.create_layout(file_id)

        try:
            file = self.files.add(
                File(
                    id=file_id,
                    filename=validated.filename,
                    file_type=validated.file_type,
                    stored_path=self.storage.relative_path(layout.original / validated.filename),
                    file_size_bytes=declared_size or 0,
                    status=FileStatus.PENDING,
                )
            )
            self.session.commit()
        except Exception:
            # No row references the directory, so nothing must be left behind.
            self.session.rollback()
            self.storage.discard(layout)
            raise
        logger.info(
            "upload.accepted",
            extra={
                "file_id": str(file_id),
                "file_type": validated.file_type.value,
                "declared_size_bytes": declared_size,
            },
        )

        try:
            self._store_and_process(file, layout, stream)
        except AppError as exc:
            self._mark_failed(file_id, exc.message)
            exc.details = {**exc.details, "file_id": str(file_id)}
            raise
        except Exception as exc:
            logger.exception("processing.unexpected_error", extra={"file_id": str(file_id)})
            self._mark_failed(file_id, GENERIC_PROCESSING_ERROR)
            raise AppError(GENERIC_PROCESSING_ERROR, details={"file_id": str(file_id)}) from exc
        finally:
            self.storage.clear_extracted(layout)
        return file

    def _store_and_process(self, file: File, layout: StorageLayout, stream: Readable) -> None:
        stored = self.storage.save_original(
            layout, file.filename, stream, max_bytes=self.validator.max_upload_bytes
        )
        file.file_size_bytes = stored.size_bytes
        file.status = FileStatus.PROCESSING
        self.session.commit()
        logger.info("processing.started", extra={"file_id": str(file.id)})

        result = self.processor.process(stored.path, file.file_type, layout.extracted)
        processed_path = self.storage.processed_geojson_path(layout)
        write_feature_collection(
            processed_path, _geojson_features(result), _geojson_metadata(file, result)
        )

        try:
            self.features.bulk_insert(_feature_rows(file.id, result))
            file.status = FileStatus.COMPLETED
            file.feature_count = result.feature_count
            file.source_crs = result.source_crs.label
            file.source_crs_assumed = result.source_crs.assumed
            file.measurement_crs = result.measurement_crs.label if result.measurement_crs else None
            file.processing_error = None
            file.completed_at = datetime.now(UTC)
            self.session.commit()
        except Exception:
            processed_path.unlink(missing_ok=True)
            raise

        logger.info(
            "processing.completed",
            extra={
                "file_id": str(file.id),
                "feature_count": result.feature_count,
                "source_crs": file.source_crs,
                "measurement_crs": file.measurement_crs,
            },
        )

    def _mark_failed(self, file_id: uuid.UUID, message: str) -> None:
        """Roll back partial work, then record FAILED in a fresh transaction."""
        self.session.rollback()
        file = self.files.get(file_id)
        if file is None:  # pragma: no cover - the PENDING row was committed earlier
            return
        file.status = FileStatus.FAILED
        file.processing_error = message
        file.feature_count = None
        file.completed_at = datetime.now(UTC)
        self.session.commit()
        logger.warning(
            "processing.failed", extra={"file_id": str(file_id), "processing_error": message}
        )


def _feature_rows(file_id: uuid.UUID, result: ProcessingResult) -> Iterator[dict[str, Any]]:
    source_label = result.source_crs.label
    measurement_label = result.measurement_crs.label if result.measurement_crs else None
    return (
        {
            "file_id": file_id,
            "feature_index": feature.feature_index,
            "source_feature_id": feature.source_feature_id,
            "source_layer": feature.source_layer,
            "geometry_type": feature.geometry_type,
            "geometry_geojson": feature.geometry,
            "display_geometry_geojson": feature.display_geometry,
            "geometry_valid": feature.measurement.geometry_valid,
            "geometry_repaired": feature.measurement.geometry_repaired,
            "properties": feature.properties,
            "source_crs": source_label,
            "measurement_crs": measurement_label,
            "measurement_type": feature.measurement.measurement_type,
            "measurement_value": feature.measurement.value,
            "measurement_unit": feature.measurement.unit,
            "measurement_status": feature.measurement.status,
            "measurement_error": feature.measurement.error,
        }
        for feature in result.features
    )


def _geojson_features(result: ProcessingResult) -> Iterator[dict[str, Any]]:
    return (_geojson_feature(feature) for feature in result.features)


def _geojson_feature(feature: ProcessedFeature) -> dict[str, Any]:
    measurement = feature.measurement
    return {
        "type": "Feature",
        "id": feature.feature_index,
        "geometry": feature.display_geometry,
        "properties": feature.properties,
        "geomeasure": {
            "feature_index": feature.feature_index,
            "source_feature_id": feature.source_feature_id,
            "source_layer": feature.source_layer,
            "geometry_type": feature.geometry_type,
            "measurement_status": measurement.status.value,
            "measurement_type": measurement.measurement_type,
            "measurement_value": measurement.value,
            "measurement_unit": measurement.unit,
        },
    }


def _geojson_metadata(file: File, result: ProcessingResult) -> dict[str, Any]:
    return {
        "file_id": str(file.id),
        "filename": file.filename,
        "display_crs": "EPSG:4326",
        "source_crs": result.source_crs.label,
        "source_crs_assumed": result.source_crs.assumed,
        "measurement_crs": result.measurement_crs.label if result.measurement_crs else None,
        "total_features": result.feature_count,
    }
