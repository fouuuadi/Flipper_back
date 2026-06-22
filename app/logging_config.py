"""Configuration du logging JSON.

Stdlib uniquement — pas de dépendance `structlog` ou `python-json-logger`.
Chaque log record est rendu comme un objet JSON sur une seule ligne, avec un
timestamp UTC ISO-8601, le niveau, le nom du logger, le message, un `exc_info`
optionnel, et tout champ supplémentaire passé via `logger.x("msg", extra={...})`.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

# Attributs issus du LogRecord standard ; tout le reste attaché à un record
# via `extra=` est traité comme un champ custom et propagé tel quel dans la
# sortie JSON.
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
    """Rend un LogRecord comme un objet JSON sur une seule ligne."""

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
    """Branche un unique StreamHandler JSON sur le root logger.

    Idempotent : chaque appel remplace les handlers existants pour que les
    reloads / les invocations répétées de `lifespan` n'accumulent pas de
    doublons.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
