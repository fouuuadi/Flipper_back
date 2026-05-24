"""HTTP request logging middleware.

Tags every request with a UUID `request_id`, measures wall-clock duration,
and emits one structured log line on completion. The id is echoed back to
the client via the `X-Request-ID` response header for end-to-end tracing.
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.responses import Response

logger = logging.getLogger("app.http")

REQUEST_ID_HEADER = "X-Request-ID"


async def http_logging_middleware(request: Request, call_next) -> Response:
    request_id = uuid.uuid4().hex
    start = time.perf_counter()
    try:
        response: Response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "http_request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration_ms, 2),
            },
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "http_request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    return response
