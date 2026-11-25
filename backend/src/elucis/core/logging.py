"""Structured logging with correlation IDs and secret redaction (SEC-17, NFR-24).

* ``LOG_FORMAT=json`` emits one JSON object per line (for files and tooling);
  ``console`` emits a readable single line for local development.
* Every record carries the current ``request_id`` (or worker ``job_id``) from a context variable.
* A redaction filter masks credentials in connection strings and values of secret-looking
  keys passed through ``extra=``. Customer text must never be logged; that is a coding rule,
  enforced in review, because no filter can recognise it reliably.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "color_message",  # uvicorn adds an ANSI-coloured copy of the message
}
_SECRET_KEY = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|cookie)")
_DSN_PASSWORD = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://[^:/@\s]+):(?P<pw>[^@\s]+)@", re.I)
_REDACTED = "***"


def redact_text(text: str) -> str:
    return _DSN_PASSWORD.sub(lambda m: f"{m.group('scheme')}:{_REDACTED}@", text)


def _redact_value(key: str, value: Any) -> Any:
    if _SECRET_KEY.search(key):
        return _REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: _redact_value(str(k), v) for k, v in value.items()}
    return value


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.msg = record.getMessage()
            record.args = None
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        for key, value in list(record.__dict__.items()):
            if key not in _RESERVED:
                record.__dict__[key] = _redact_value(key, value)
        return True


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.job_id = job_id_var.get()
        return True


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    return {
        k: v
        for k, v in record.__dict__.items()
        if k not in _RESERVED and k not in {"request_id", "job_id"} and not k.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "job_id"):
            value = getattr(record, key, None)
            if value:
                payload[key] = value
        payload.update(_extras(record))
        if record.exc_info:
            payload["exc"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, UTC).strftime("%H:%M:%S.%f")[:-3]
        ctx = getattr(record, "request_id", None) or getattr(record, "job_id", None)
        extras = " ".join(f"{k}={v}" for k, v in _extras(record).items())
        line = f"{ts} {record.levelname:<7} {record.name}: {record.getMessage()}"
        if ctx:
            line += f" [{ctx}]"
        if extras:
            line += f" {extras}"
        if record.exc_info:
            line += "\n" + redact_text(self.formatException(record.exc_info))
        return line


def configure_logging(level: str = "INFO", fmt: str = "console") -> None:
    """Configure the root logger once; uvicorn's loggers propagate into it."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JsonFormatter() if fmt == "json" else ConsoleFormatter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # Our middleware writes the access log; uvicorn's would duplicate it without request IDs.
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
    access.disabled = True
    for noisy in ("httpx2", "httpcore", "multipart"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))
