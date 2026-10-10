"""Workspace statistics and public service configuration."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import MeasurementServiceDep, SettingsDep
from app.geospatial.crs import MAX_LINEAR_DISTORTION
from app.schemas.system import MeasurementSettings, ServiceInfo, UploadLimits, WorkspaceStats
from app.version import __version__ as API_VERSION

router = APIRouter(tags=["system"])

CRS_STRATEGY = [
    "Source CRS, if projected with a metric-convertible unit and distortion within the limit",
    "WGS 84 UTM zone containing the dataset centre",
    "Transverse Mercator centred on the dataset",
    "Lambert Azimuthal Equal-Area centred on the dataset (continent-scale extents)",
]


@router.get("/stats", response_model=WorkspaceStats, summary="Workspace statistics")
def stats(service: MeasurementServiceDep) -> WorkspaceStats:
    """File counts by state and feature/measurement totals across all completed files."""
    return service.workspace_stats()


@router.get("/meta", response_model=ServiceInfo, summary="Public service configuration")
def meta(settings: SettingsDep) -> ServiceInfo:
    """Limits and measurement behaviour clients should know about (no secrets)."""
    return ServiceInfo(
        name=settings.app_name,
        version=API_VERSION,
        environment=settings.app_env.value,
        upload=UploadLimits(
            max_upload_size_mb=settings.max_upload_size_mb,
            max_upload_bytes=settings.max_upload_bytes,
            allowed_extensions=sorted(settings.allowed_extensions),
        ),
        measurement=MeasurementSettings(
            max_linear_distortion=MAX_LINEAR_DISTORTION, crs_strategy=CRS_STRATEGY
        ),
        geojson_preview_max_features=settings.geojson_preview_max_features,
    )
