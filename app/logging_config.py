"""JSON logging configuration.

Stdlib only — no `structlog` or `python-json-logger` dependency. Every log
record is rendered as a single-line JSON object with a UTC ISO-8601
timestamp, the level, the logger name, the message, optional `exc_info`,
and any extra fields passed via `logger.x("msg", extra={...})`.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

# Attributes that come from the standard LogRecord; everything else attached
# to a record via `extra=` is treated as a custom field and propagated to the
# JSON output verbatim.
_STANDARD_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "taskName",
        "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """Render LogRecord as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Wire a single JSON StreamHandler on the root logger.

    Idempotent: every call replaces the existing handlers so reloads /
    repeated `lifespan` invocations don't accumulate duplicates.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
