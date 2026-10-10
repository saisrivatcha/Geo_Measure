from __future__ import annotations

import json
import logging

from app.core.logging import JsonFormatter, RequestIdFilter, TextFormatter, request_id_ctx


def _record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "upload.accepted", None, None)
    record.__dict__.update(extra)
    RequestIdFilter().filter(record)
    return record


def test_json_formatter_includes_request_id_and_structured_fields() -> None:
    token = request_id_ctx.set("req-123")
    try:
        record = _record(file_id="abc", feature_count=4)
    finally:
        request_id_ctx.reset(token)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "upload.accepted"
    assert payload["request_id"] == "req-123"
    assert payload["level"] == "INFO"
    assert payload["file_id"] == "abc"
    assert payload["feature_count"] == 4


def test_text_formatter_renders_key_values_and_default_request_id() -> None:
    line = TextFormatter().format(_record(file_id="abc"))
    assert "[-] app.test: upload.accepted" in line
    assert line.endswith("file_id=abc")
