"""Application factory.

``create_app`` wires configuration, logging, middleware, error handling and
routers. Uvicorn runs it as a factory (``uvicorn app.main:create_app --factory``)
and tests call ``create_app(settings)`` with their own settings.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.error_handlers import register_error_handlers
from app.api.openapi import TAGS
from app.api.routes import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.middleware import (
    REQUEST_ID_HEADER,
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
)
from app.db.session import build_engine, build_session_factory
from app.version import __version__ as API_VERSION

logger = logging.getLogger(__name__)

API_DESCRIPTION = """
Upload a **KML** document or a **ZIP containing one ESRI Shapefile**; GeoMeasure
extracts every feature (geometry type, geometry, CRS, properties) and measures
polygons (area, m²) and lines (length, m).

**Measurement CRS.** Coordinates are never measured in degrees. Geographic data
is projected to the UTM zone of the dataset (or a dataset-centred projection
when it spans zones); projected data is measured in its own CRS when that CRS's
scale distortion over the data is below 0.1 %, otherwise reprojected the same way.
Data without a CRS is not measured (`CRS_UNAVAILABLE`).

**Errors** always use the envelope
`{"error": {"code": "...", "message": "...", "details": {...}}}` and every
response carries an `X-Request-ID` header.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        engine = build_engine(settings.database_url, echo=settings.database_echo)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = build_session_factory(engine)
        logger.info(
            "app.started",
            extra={"app_env": settings.app_env.value, "storage_dir": str(settings.storage_dir)},
        )
        try:
            yield
        finally:
            engine.dispose()
            logger.info("app.stopped")

    app = FastAPI(
        title=settings.app_name,
        version=API_VERSION,
        description=API_DESCRIPTION,
        openapi_tags=TAGS,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/api/openapi.json",
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=[REQUEST_ID_HEADER],
        )
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=settings.max_request_body_bytes)
    # Added last so it is the outermost middleware and wraps everything, CORS included.
    app.add_middleware(RequestContextMiddleware)

    register_error_handlers(app)
    app.include_router(api_router)
    if not settings.is_production:

        @app.get("/docs", include_in_schema=False)
        def docs_redirect() -> RedirectResponse:
            """Convenience alias: the interactive docs live under /api so they are
            reachable through the same proxy as the API."""
            return RedirectResponse("/api/docs")

    return app
