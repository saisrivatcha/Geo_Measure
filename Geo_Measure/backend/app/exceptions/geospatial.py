"""Errors raised by the geospatial processing pipeline.

These fail a whole file. Problems with individual features (unsupported or
invalid geometry, missing CRS) are never exceptions: they become per-feature
measurement statuses so the rest of the file is still processed.
"""

from __future__ import annotations

from http import HTTPStatus

from app.exceptions.base import AppError


class GeospatialProcessingError(AppError):
    code = "GEOSPATIAL_PROCESSING_ERROR"
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    default_message = "The geospatial dataset could not be processed."


class DatasetReadError(GeospatialProcessingError):
    code = "DATASET_UNREADABLE"
    default_message = "The dataset could not be read. The file may be corrupt or incomplete."


class EmptyDatasetError(GeospatialProcessingError):
    code = "EMPTY_DATASET"
    default_message = "The dataset contains no features."
