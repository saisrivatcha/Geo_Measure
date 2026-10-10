"""Enumerations persisted as PostgreSQL ENUM types (value == name)."""

from __future__ import annotations

from enum import StrEnum


class FileType(StrEnum):
    KML = "KML"
    SHAPEFILE = "SHAPEFILE"


class FileStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MeasurementType(StrEnum):
    LENGTH = "LENGTH"
    AREA = "AREA"


class MeasurementStatus(StrEnum):
    """Outcome of measuring a single feature.

    Only ``COMPLETED`` carries a value. Every other status explains why not:

    * ``NOT_REQUIRED``     - points have no length or area.
    * ``NOT_SUPPORTED``    - geometry collections and unknown types.
    * ``NO_GEOMETRY``      - the feature has a null or empty geometry.
    * ``INVALID_GEOMETRY`` - invalid and could not be safely repaired.
    * ``CRS_UNAVAILABLE``  - the source CRS is unknown, so metric values would be invented.
    * ``FAILED``           - measurement was attempted but the result is unusable
      (e.g. coordinates outside the declared CRS's valid range).
    """

    COMPLETED = "COMPLETED"
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NO_GEOMETRY = "NO_GEOMETRY"
    INVALID_GEOMETRY = "INVALID_GEOMETRY"
    CRS_UNAVAILABLE = "CRS_UNAVAILABLE"
    FAILED = "FAILED"


class MeasurementUnit(StrEnum):
    SQUARE_METERS = "square_meters"
    METERS = "meters"
