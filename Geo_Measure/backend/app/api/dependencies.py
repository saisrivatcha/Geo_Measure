"""FastAPI dependency providers.

Settings, the engine and the session factory are created once in the app
lifespan and held on ``app.state``; these providers hand them to routes, and
tests can override any of them via ``app.dependency_overrides``. Services are
built per request around the request's session.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.geospatial.processor import GeospatialProcessor
from app.geospatial.validators import FileValidator
from app.repositories.feature_measurement_repository import FeatureMeasurementRepository
from app.repositories.file_repository import FileRepository
from app.services.file_service import FileService
from app.services.measurement_service import MeasurementService
from app.services.storage import FileStorage


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_db_session(request: Request) -> Iterator[Session]:
    """One session per request; rolled back on error, always closed."""
    session: Session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
EngineDep = Annotated[Engine, Depends(get_engine)]
SessionDep = Annotated[Session, Depends(get_db_session)]


def get_file_validator(settings: SettingsDep) -> FileValidator:
    return FileValidator(
        allowed_extensions=settings.allowed_extensions,
        max_upload_bytes=settings.max_upload_bytes,
        max_extracted_bytes=settings.max_extracted_bytes,
    )


def get_file_service(
    session: SessionDep,
    settings: SettingsDep,
    validator: Annotated[FileValidator, Depends(get_file_validator)],
) -> FileService:
    return FileService(
        session=session,
        files=FileRepository(session),
        features=FeatureMeasurementRepository(session),
        storage=FileStorage(settings.storage_dir),
        validator=validator,
        processor=GeospatialProcessor(validator),
    )


def get_measurement_service(session: SessionDep, settings: SettingsDep) -> MeasurementService:
    return MeasurementService(
        FileRepository(session),
        FeatureMeasurementRepository(session),
        preview_max_features=settings.geojson_preview_max_features,
    )


FileServiceDep = Annotated[FileService, Depends(get_file_service)]
MeasurementServiceDep = Annotated[MeasurementService, Depends(get_measurement_service)]
