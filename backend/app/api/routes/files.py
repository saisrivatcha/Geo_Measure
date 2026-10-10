"""Upload, inspect and read results of geospatial files.

Every path is served with and without a trailing slash (``/api/files`` and
``/api/files/``) without redirects; only the trailing-slash form appears in the
OpenAPI document. Route handlers only translate HTTP to service calls.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, File, Path, Query, Response, UploadFile, status

from app.api.dependencies import FileServiceDep, MeasurementServiceDep
from app.api.openapi import error_responses
from app.db.models import FileStatus, FileType
from app.repositories.file_repository import FileSortField, SortOrder
from app.schemas.files import FileLinks, FileList, FileProcessingResult, FileRead
from app.schemas.geojson import FeatureCollection
from app.schemas.measurements import FeatureDetail, MeasurementsPage

router = APIRouter(prefix="/files", tags=["files"])

MAX_FILES_PAGE_SIZE = 100
MAX_MEASUREMENTS_PAGE_SIZE = 500

FileId = Annotated[uuid.UUID, Path(description="File ID returned by the upload endpoint.")]
Page = Annotated[int, Query(ge=1, description="1-based page number.")]


def _route(
    method: str, path: str, **kwargs: Any
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register ``path`` (documented) and its slash twin (hidden) for one handler."""
    twin = path[:-1] if path.endswith("/") else f"{path}/"

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        router.api_route(path, methods=[method], **kwargs)(func)
        router.api_route(twin, methods=[method], include_in_schema=False, **kwargs)(func)
        return func

    return decorator


def _links(file_id: uuid.UUID) -> FileLinks:
    base = f"/api/files/{file_id}"
    return FileLinks(
        self=f"{base}/", measurements=f"{base}/measurements/", geojson=f"{base}/geojson"
    )


@_route(
    "POST",
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=FileProcessingResult,
    summary="Upload and process a KML or zipped Shapefile",
    responses=error_responses(400, 413, 415, 422, 500),
)
def upload_file(
    response: Response,
    service: FileServiceDep,
    measurements: MeasurementServiceDep,
    file: Annotated[
        UploadFile,
        File(
            description="A `.kml` document, or a `.zip` containing exactly one Shapefile "
            "(`.shp`, `.shx`, `.dbf`; `.prj` and `.cpg` optional)."
        ),
    ],
) -> FileProcessingResult:
    """Validates, stores and processes the upload synchronously, then returns the
    result.

    For each feature the service records the geometry, properties, geometry
    validity and - for polygons and lines - the area (m²) or length (m),
    computed in a projected CRS chosen for the dataset's location. Coordinates
    are never measured in degrees.

    Errors raised after the file was stored include `details.file_id`; that file
    is then `FAILED` and can be inspected with `GET /api/files/{id}/`.
    """
    stored = service.upload(file.filename, file.file, file.size)
    response.headers["Location"] = f"/api/files/{stored.id}/"
    return FileProcessingResult(
        file=FileRead.model_validate(stored),
        summary=measurements.summary(stored.id),
        links=_links(stored.id),
    )


@_route(
    "GET",
    "/",
    response_model=FileList,
    summary="List uploaded files",
    responses=error_responses(422),
)
def list_files(
    service: FileServiceDep,
    page: Page = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_FILES_PAGE_SIZE)] = 20,
    sort: Annotated[FileSortField, Query(description="Sort field.")] = FileSortField.CREATED_AT,
    order: Annotated[SortOrder, Query(description="Sort direction.")] = SortOrder.DESC,
    status: Annotated[FileStatus | None, Query(description="Only files in this state.")] = None,
    file_type: Annotated[FileType | None, Query(description="Only KML or SHAPEFILE.")] = None,
    q: Annotated[
        str | None,
        Query(max_length=200, description="Case-insensitive substring of the filename."),
    ] = None,
) -> FileList:
    """Paginated file metadata, newest first by default."""
    rows, total = service.list_files(
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
        status=status,
        file_type=file_type,
        search=q.strip() if q and q.strip() else None,
    )
    return FileList(
        items=[FileRead.model_validate(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size),
    )


@_route(
    "GET",
    "/{file_id}/",
    response_model=FileRead,
    summary="Get a file's metadata and processing status",
    responses=error_responses(404, 422),
)
def get_file(file_id: FileId, service: FileServiceDep) -> FileRead:
    """Metadata of one upload: status, feature count, source and measurement CRS
    (codes and names) and, for FAILED files, the reason."""
    return FileRead.model_validate(service.get_file(file_id))


@_route(
    "GET",
    "/{file_id}/measurements/",
    response_model=MeasurementsPage,
    summary="Get per-feature measurements with a summary",
    responses=error_responses(404, 409, 422),
)
def get_measurements(
    file_id: FileId,
    service: MeasurementServiceDep,
    page: Page = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_MEASUREMENTS_PAGE_SIZE)] = 50,
) -> MeasurementsPage:
    """Features in `feature_index` order. `measurement` is null unless
    `measurement_status` is `COMPLETED`; other statuses explain why:
    `NOT_REQUIRED` (points), `NOT_SUPPORTED` (collections), `NO_GEOMETRY`,
    `INVALID_GEOMETRY` (unrepairable), `CRS_UNAVAILABLE` (no CRS, e.g. a
    Shapefile without `.prj`), `FAILED`. The summary always covers the whole file.
    """
    return service.measurements_page(file_id, page=page, page_size=page_size)


@_route(
    "GET",
    "/{file_id}/geojson",
    response_model=FeatureCollection,
    summary="Get features as a GeoJSON FeatureCollection for map display",
    responses=error_responses(404, 409, 422),
)
def get_geojson(
    file_id: FileId,
    service: MeasurementServiceDep,
    limit: Annotated[
        int | None,
        Query(
            ge=1,
            description="Return at most this many features (never more than the "
            "server cap, GEOJSON_PREVIEW_MAX_FEATURES).",
        ),
    ] = None,
) -> FeatureCollection:
    """Geometries are reprojected to EPSG:4326 (RFC 7946) for display only; the
    stored source and measurement CRSs are unchanged. Large datasets are capped
    and `metadata.truncated` says so. Each feature carries its measurement in
    the `geomeasure` member.
    """
    return service.geojson_preview(file_id, limit=limit)


@_route(
    "GET",
    "/{file_id}/features/{feature_index}",
    response_model=FeatureDetail,
    summary="Get one feature with its geometry",
    responses=error_responses(404, 409, 422),
)
def get_feature(
    file_id: FileId,
    feature_index: Annotated[int, Path(ge=0, description="Zero-based feature_index.")],
    service: MeasurementServiceDep,
) -> FeatureDetail:
    """Measurement, properties and geometry (source CRS and EPSG:4326) of one feature."""
    return service.feature_detail(file_id, feature_index)
