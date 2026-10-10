"""Root of the application exception hierarchy.

Each subclass declares a stable machine-readable ``code`` and an HTTP status.
The API layer translates any :class:`AppError` into the standard error envelope;
services and the geospatial package never import FastAPI.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any, ClassVar


class AppError(Exception):
    code: ClassVar[str] = "INTERNAL_ERROR"
    status_code: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR
    default_message: ClassVar[str] = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None):
        self.message = message or self.default_message
        self.details: dict[str, Any] = details or {}
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"
