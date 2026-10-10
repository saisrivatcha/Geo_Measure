"""Liveness and readiness probes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import EngineDep
from app.api.openapi import error_responses
from app.db.session import ping
from app.schemas.errors import error_payload
from app.schemas.health import HealthResponse, ReadinessResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """The process is up and serving requests. Does not touch dependencies."""
    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses=error_responses(503),
    summary="Readiness probe",
)
def readiness(engine: EngineDep) -> ReadinessResponse | JSONResponse:
    """The service can reach PostgreSQL and is ready to accept work."""
    try:
        ping(engine)
    except SQLAlchemyError:
        logger.warning("health.database_unavailable", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_payload("DATABASE_UNAVAILABLE", "The database is not reachable."),
        )
    return ReadinessResponse()
