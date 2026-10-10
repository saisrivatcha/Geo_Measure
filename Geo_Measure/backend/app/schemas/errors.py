"""The single error envelope returned by every failing endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str = Field(examples=["INVALID_FILE_TYPE"])
    message: str = Field(examples=["Only .kml and .zip Shapefile uploads are supported."])
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details or {})
    ).model_dump(mode="json")
