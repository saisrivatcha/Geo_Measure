from app.exceptions.base import AppError
from app.exceptions.files import (
    AmbiguousShapefileError,
    EmptyFileError,
    FeatureNotFoundError,
    FileNotProcessedError,
    FileRecordNotFoundError,
    FileTooLargeError,
    InvalidArchiveError,
    InvalidFilenameError,
    InvalidFileTypeError,
    InvalidKMLError,
    MissingShapefileComponentsError,
    StorageError,
    UnsafeArchiveError,
)
from app.exceptions.geospatial import (
    DatasetReadError,
    EmptyDatasetError,
    GeospatialProcessingError,
)

__all__ = [
    "AmbiguousShapefileError",
    "AppError",
    "DatasetReadError",
    "EmptyDatasetError",
    "EmptyFileError",
    "FeatureNotFoundError",
    "FileNotProcessedError",
    "FileRecordNotFoundError",
    "FileTooLargeError",
    "GeospatialProcessingError",
    "InvalidArchiveError",
    "InvalidFileTypeError",
    "InvalidFilenameError",
    "InvalidKMLError",
    "MissingShapefileComponentsError",
    "StorageError",
    "UnsafeArchiveError",
]
