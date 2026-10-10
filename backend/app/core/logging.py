"""Structured logging with a per-request correlation ID.

Every record gets a ``request_id`` attribute (``-`` outside a request) from a
context variable set by :class:`app.core.middleware.RequestContextMiddleware`.
Structured fields are passed through ``extra={...}`` and rendered either as a JSON
object per line (production/Docker) or as ``key=value`` pairs (local terminals).
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

NO_REQUEST_ID = "-"

request_id_ctx: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST_ID)

# Attributes present on every LogRecord; anything else came from ``extra``.
_RESERVED_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()
    | {"message", "asctime", "request_id", "taskName", "color_message"}
)


class RequestIdFilter(logging.Filter):
    """Attach the current request ID to a record if it does not have one yet."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_ctx.get()
        return True


def _install_record_factory() -> None:
    """Stamp ``request_id`` on records at creation time.

    Doing it in the record factory (rather than only in a handler filter) means
    every handler - including pytest's ``caplog`` - sees the same ID, and the ID
    is captured in the context where the log call happened.
    """
    current = logging.getLogRecordFactory()
    if getattr(current, "_geomeasure", False):
        return

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = current(*args, **kwargs)
        record.request_id = request_id_ctx.get()
        return record

    factory._geomeasure = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    return {k: v for k, v in record.__dict__.items() if k not in _RESERVED_ATTRS}


class JsonFormatter(logging.Formatter):
    """One JSON object per line; safe for log shippers."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", NO_REQUEST_ID),
            **_extra_fields(record),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable single line with trailing ``key=value`` fields."""

    def __init__(self) -> None:
        super().__init__(
            "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        extras = _extra_fields(record)
        if extras:
            line += " " + " ".join(f"{k}={v}" for k, v in extras.items())
        return line


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Install a single stdout handler on the root logger (idempotent)."""
    _install_record_factory()
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, "_geomeasure", False):
            root.removeHandler(existing)
    handler._geomeasure = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn's access log duplicates our request logs; route its error log through
    # the root handler so it carries request IDs and the same format.
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
