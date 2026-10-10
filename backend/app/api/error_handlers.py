"""Translate exceptions into the standard error envelope.

Unexpected exceptions are handled by :class:`RequestContextMiddleware`, which
logs the traceback with the request ID and returns a generic 500 body.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.middleware import BodyTooLargeError
from app.exceptions import AppError, FileTooLargeError
from app.schemas.errors import error_payload

logger = logging.getLogger(__name__)

_HTTP_STATUS_CODES: dict[int, str] = {
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: FileTooLargeError.code,
}


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    level = logging.ERROR if exc.status_code >= 500 else logging.WARNING
    logger.log(
        level,
        "request.rejected",
        extra={"error_code": exc.code, "status_code": exc.status_code, "path": request.url.path},
        exc_info=exc if exc.status_code >= 500 else None,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [_simplify_validation_error(error) for error in exc.errors()]
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content=error_payload("VALIDATION_ERROR", "The request is invalid.", {"errors": errors}),
    )


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    details = {"max_bytes": exc.max_body_bytes} if isinstance(exc, BodyTooLargeError) else {}
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code, message, details),
        headers=getattr(exc, "headers", None),
    )


def _simplify_validation_error(error: Any) -> dict[str, Any]:
    """Keep location, message and type; drop echoed input values."""
    return {
        "loc": [str(part) for part in error.get("loc", ())],
        "message": error.get("msg", ""),
        "type": error.get("type", ""),
    }


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)  # type: ignore[arg-type]
