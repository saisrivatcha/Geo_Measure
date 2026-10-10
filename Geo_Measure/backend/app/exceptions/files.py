"""Errors raised while accepting, validating, storing or looking up uploads."""

from __future__ import annotations

from http import HTTPStatus

from app.exceptions.base import AppError


class InvalidFileTypeError(AppError):
    code = "INVALID_FILE_TYPE"
    status_code = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    default_message = "Only .kml and .zip Shapefile uploads are supported."


class EmptyFileError(AppError):
    code = "EMPTY_FILE"
    status_code = HTTPStatus.BAD_REQUEST
    default_message = "The uploaded file is empty."


class FileTooLargeError(AppError):
    code = "FILE_TOO_LARGE"
    status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    default_message = "The uploaded file exceeds the maximum allowed size."


class InvalidFilenameError(AppError):
    code = "INVALID_FILENAME"
    status_code = HTTPStatus.BAD_REQUEST
    default_message = "The uploaded file has a missing or unsafe filename."


class InvalidKMLError(AppError):
    code = "INVALID_KML"
    status_code = HTTPStatus.BAD_REQUEST
    default_message = "The uploaded file is not a valid KML document."


class InvalidArchiveError(AppError):
    code = "INVALID_ARCHIVE"
    status_code = HTTPStatus.BAD_REQUEST
    default_message = "The uploaded file is not a valid ZIP archive."


class UnsafeArchiveError(InvalidArchiveError):
    code = "UNSAFE_ARCHIVE"
    default_message = "The archive contains unsafe entries and was rejected."


class AmbiguousShapefileError(InvalidArchiveError):
    code = "AMBIGUOUS_SHAPEFILE"
    default_message = "The archive contains more than one Shapefile; upload one per ZIP."


class MissingShapefileComponentsError(InvalidArchiveError):
    code = "MISSING_SHAPEFILE_COMPONENTS"
    default_message = "The archive is missing required Shapefile components."


class FileRecordNotFoundError(AppError):
    """No upload exists for the requested ID.

    Named to avoid shadowing the built-in ``FileNotFoundError``; the API code is
    ``FILE_NOT_FOUND``.
    """

    code = "FILE_NOT_FOUND"
    status_code = HTTPStatus.NOT_FOUND
    default_message = "File not found."


class FeatureNotFoundError(AppError):
    code = "FEATURE_NOT_FOUND"
    status_code = HTTPStatus.NOT_FOUND
    default_message = "Feature not found."


class FileNotProcessedError(AppError):
    """The file exists but has no results (still processing, or processing failed)."""

    code = "FILE_NOT_PROCESSED"
    status_code = HTTPStatus.CONFLICT
    default_message = "The file has not been processed successfully."


class StorageError(AppError):
    code = "STORAGE_ERROR"
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    default_message = "The file could not be stored."
