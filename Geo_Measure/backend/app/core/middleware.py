"""Request context middleware: request IDs, access logging, last-resort errors.

Implemented as a plain ASGI middleware (not ``BaseHTTPMiddleware``) so the
request-ID context variable is visible to every log call made while handling
the request, including the unhandled-exception path.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_ctx
from app.exceptions import AppError, FileTooLargeError
from app.schemas.errors import error_payload

logger = logging.getLogger("app.request")

REQUEST_ID_HEADER = "x-request-id"
_VALID_INBOUND_ID = re.compile(r"^[A-Za-z0-9._\-]{1,128}$")

INTERNAL_ERROR_BODY = json.dumps(error_payload(AppError.code, AppError.default_message)).encode()


def _resolve_request_id(scope: Scope) -> str:
    """Reuse a well-formed inbound ID (e.g. from a proxy), otherwise mint one."""
    for name, value in scope.get("headers", []):
        if name == REQUEST_ID_HEADER.encode():
            candidate = value.decode("latin-1")
            if _VALID_INBOUND_ID.match(candidate):
                return candidate
            break
    return uuid.uuid4().hex


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(scope)
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        method, path = scope["method"], scope["path"]
        logger.info("request.started", extra={"method": method, "path": path})
        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception("request.unhandled_error", extra={"method": method, "path": path})
            if response_started:
                raise
            status_code = 500
            await self._send_internal_error(send_with_request_id)
        finally:
            logger.info(
                "request.completed",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            request_id_ctx.reset(token)

    @staticmethod
    async def _send_internal_error(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(INTERNAL_ERROR_BODY)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": INTERNAL_ERROR_BODY})


class BodyTooLargeError(StarletteHTTPException):
    """Raised from ``receive`` mid-stream. An HTTPException so that FastAPI's body
    parsing re-raises it as-is (it converts other errors into a generic 400)."""

    def __init__(self, max_body_bytes: int) -> None:
        super().__init__(status_code=413, detail=FileTooLargeError.default_message)
        self.max_body_bytes = max_body_bytes


class BodySizeLimitMiddleware:
    """Reject request bodies above ``max_body_bytes`` before they are parsed.

    A declared ``Content-Length`` over the limit is refused without parsing; for
    chunked bodies the bytes are counted as they arrive. This stops an oversized
    multipart upload from being spooled to disk in full before validation runs.

    Before answering 413 the remaining body is read and discarded, up to
    ``DRAIN_FACTOR`` times the limit. Closing the connection while a reverse
    proxy (nginx) is still forwarding the body makes the proxy report 502
    instead of passing the 413 on; larger bodies are not drained and the
    connection is simply closed after the response.
    """

    DRAIN_FACTOR = 2

    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.drain_limit = max_body_bytes * self.DRAIN_FACTOR

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared is not None and declared > self.max_body_bytes:
            if declared <= self.drain_limit:
                await _drain(receive, self.drain_limit)
            await self._reject(send)
            return

        received = 0
        body_complete = False
        over_limit = False
        response_started = False

        async def counting_receive() -> Message:
            nonlocal received, body_complete, over_limit
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                body_complete = not message.get("more_body", False)
                if received > self.max_body_bytes:
                    over_limit = True
                    raise BodyTooLargeError(self.max_body_bytes)
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                if over_limit and not body_complete:
                    await _drain(receive, self.drain_limit - received)
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except BodyTooLargeError:
            if response_started:
                raise
            if not body_complete:
                await _drain(receive, self.drain_limit - received)
            await self._reject(send)

    async def _reject(self, send: Send) -> None:
        logger.warning("request.body_too_large", extra={"max_body_bytes": self.max_body_bytes})
        body = json.dumps(
            error_payload(
                FileTooLargeError.code,
                FileTooLargeError.default_message,
                {"max_bytes": self.max_body_bytes},
            )
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


async def _drain(receive: Receive, limit: int) -> None:
    """Read and discard request body chunks until the body ends or ``limit`` bytes."""
    drained = 0
    while drained <= limit:
        message = await receive()
        if message["type"] != "http.request":
            return
        drained += len(message.get("body", b""))
        if not message.get("more_body", False):
            return


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None
