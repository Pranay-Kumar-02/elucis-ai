from __future__ import annotations

import json
import logging

from elucis.core.logging import (
    ContextFilter,
    JsonFormatter,
    RedactionFilter,
    redact_text,
    request_id_var,
)


def _record(msg: str, *args: object, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, msg, args, None)
    record.__dict__.update(extra)
    return record


def test_redact_text_masks_dsn_password() -> None:
    assert (
        redact_text("connect postgresql+psycopg://app_api:hunter2@db:5432/x failed")
        == "connect postgresql+psycopg://app_api:***@db:5432/x failed"
    )


def test_redaction_filter_masks_args_and_secret_extras() -> None:
    record = _record("url=%s", "postgresql://u:pw@h/d", api_key="abc", password="p", count=3)
    RedactionFilter().filter(record)
    assert record.getMessage() == "url=postgresql://u:***@h/d"
    assert record.api_key == "***"
    assert record.password == "***"
    assert record.count == 3


def test_json_formatter_includes_request_id_and_extras() -> None:
    token = request_id_var.set("01TESTREQUESTID000000000000")
    try:
        record = _record("hello", duration_ms=1.5)
        ContextFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert payload["msg"] == "hello"
    assert payload["request_id"] == "01TESTREQUESTID000000000000"
    assert payload["duration_ms"] == 1.5
    assert payload["level"] == "INFO"
