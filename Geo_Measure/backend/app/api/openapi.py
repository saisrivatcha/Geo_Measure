"""OpenAPI documentation helpers: tag descriptions and documented error responses.

Every error response shares the :class:`ErrorResponse` envelope; these helpers
attach realistic, named examples per status code so Swagger UI shows exactly
what a client receives.
"""

from __future__ import annotations

from typing import Any

from app.schemas.errors import ErrorResponse, error_payload

FILE_ID_EXAMPLE = "c65e3449-1428-4fab-9daf-9ee8746b98d3"

TAGS: list[dict[str, str]] = [
    {
        "name": "files",
        "description": "Upload KML or zipped Shapefile datasets and read their features, "
        "measurements and map-ready GeoJSON.",
    },
    {"name": "system", "description": "Workspace statistics and public service configuration."},
    {"name": "health", "description": "Liveness and readiness probes."},
]

_EXAMPLES: dict[int, tuple[str, dict[str, dict[str, Any]]]] = {
    400: (
        "The upload or its dataset is invalid. Errors raised after the file was stored "
        "include `details.file_id`; that file is then FAILED.",
        {
            "invalid_archive": {
                "summary": "Corrupt ZIP",
                "value": error_payload(
                    "INVALID_ARCHIVE",
                    "The uploaded file is not a valid ZIP archive.",
                    {"file_id": FILE_ID_EXAMPLE},
                ),
            },
            "missing_components": {
                "summary": "Shapefile without .dbf",
                "value": error_payload(
                    "MISSING_SHAPEFILE_COMPONENTS",
                    "Shapefile 'parcels.shp' is missing: .dbf.",
                    {"shapefile": "parcels.shp", "missing": [".dbf"], "file_id": FILE_ID_EXAMPLE},
                ),
            },
            "unsafe_archive": {
                "summary": "Path traversal in ZIP",
                "value": error_payload(
                    "UNSAFE_ARCHIVE",
                    "The archive contains unsafe entries and was rejected.",
                    {"member": "../../etc/evil.shp", "file_id": FILE_ID_EXAMPLE},
                ),
            },
            "invalid_kml": {
                "summary": "Malformed KML",
                "value": error_payload(
                    "INVALID_KML",
                    "The KML document is not well-formed XML.",
                    {"line": 3, "reason": "no element found", "file_id": FILE_ID_EXAMPLE},
                ),
            },
            "empty_file": {
                "summary": "Empty upload",
                "value": error_payload("EMPTY_FILE", "The uploaded file is empty."),
            },
        },
    ),
    404: (
        "No file (or feature) with this ID.",
        {
            "file_not_found": {
                "summary": "Unknown file",
                "value": error_payload(
                    "FILE_NOT_FOUND", "File not found.", {"file_id": FILE_ID_EXAMPLE}
                ),
            },
            "feature_not_found": {
                "summary": "Unknown feature index",
                "value": error_payload(
                    "FEATURE_NOT_FOUND",
                    "Feature not found.",
                    {"file_id": FILE_ID_EXAMPLE, "feature_index": 9999},
                ),
            },
        },
    ),
    409: (
        "The file is PENDING, PROCESSING or FAILED, so it has no results.",
        {
            "not_processed": {
                "summary": "Failed file",
                "value": error_payload(
                    "FILE_NOT_PROCESSED",
                    "The file is FAILED; results are only available once COMPLETED.",
                    {
                        "file_id": FILE_ID_EXAMPLE,
                        "status": "FAILED",
                        "processing_error": "The uploaded file is not a valid ZIP archive.",
                    },
                ),
            },
        },
    ),
    413: (
        "The request body exceeds MAX_UPLOAD_SIZE_MB.",
        {
            "too_large": {
                "summary": "Upload over the limit",
                "value": error_payload(
                    "FILE_TOO_LARGE",
                    "The uploaded file exceeds the maximum allowed size.",
                    {"size_bytes": 73400320, "max_bytes": 52428800},
                ),
            },
        },
    ),
    415: (
        "Only .kml and .zip are accepted.",
        {
            "kmz": {
                "summary": "KMZ upload",
                "value": error_payload(
                    "INVALID_FILE_TYPE",
                    "KMZ archives are not supported. Extract the .kml and upload it directly.",
                    {"extension": ".kmz", "allowed": [".kml", ".zip"]},
                ),
            },
        },
    ),
    422: (
        "Invalid request parameters, or a readable upload whose dataset cannot be processed.",
        {
            "validation": {
                "summary": "Invalid parameter",
                "value": error_payload(
                    "VALIDATION_ERROR",
                    "The request is invalid.",
                    {
                        "errors": [
                            {
                                "loc": ["query", "page_size"],
                                "message": "Input should be less than or equal to 500",
                                "type": "less_than_equal",
                            }
                        ]
                    },
                ),
            },
            "empty_dataset": {
                "summary": "No features",
                "value": error_payload(
                    "EMPTY_DATASET",
                    "The KML document contains no placemarks.",
                    {"file_id": FILE_ID_EXAMPLE},
                ),
            },
        },
    ),
    500: (
        "Unexpected failure. Details are logged with the request ID, never returned.",
        {
            "internal": {
                "summary": "Unexpected error",
                "value": error_payload(
                    "INTERNAL_ERROR",
                    "An unexpected error occurred while processing the file.",
                    {"file_id": FILE_ID_EXAMPLE},
                ),
            },
        },
    ),
    503: (
        "The API is running but cannot reach PostgreSQL.",
        {
            "database": {
                "summary": "Database down",
                "value": error_payload("DATABASE_UNAVAILABLE", "The database is not reachable."),
            },
        },
    ),
}


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses`` entries for the given error status codes."""
    responses: dict[int | str, dict[str, Any]] = {}
    for status_code in status_codes:
        description, examples = _EXAMPLES[status_code]
        responses[status_code] = {
            "model": ErrorResponse,
            "description": description,
            "content": {"application/json": {"examples": examples}},
        }
    return responses
