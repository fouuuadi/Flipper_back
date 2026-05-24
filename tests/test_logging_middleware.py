import logging
import re

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.transport.http.logging_middleware import REQUEST_ID_HEADER


@pytest.mark.asyncio
async def test_request_emits_log_with_expected_fields(caplog):
    caplog.set_level(logging.INFO, logger="app.http")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200

    matching = [r for r in caplog.records if r.message == "http_request"]
    assert matching, "no http_request log emitted"
    record = matching[-1]
    assert record.method == "GET"
    assert record.path == "/health"
    assert record.status_code == 200
    assert isinstance(record.duration_ms, (int, float))
    assert record.duration_ms >= 0
    assert re.fullmatch(r"[0-9a-f]{32}", record.request_id)


@pytest.mark.asyncio
async def test_response_carries_request_id_header():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    header_value = response.headers.get(REQUEST_ID_HEADER)
    assert header_value is not None
    assert re.fullmatch(r"[0-9a-f]{32}", header_value)


@pytest.mark.asyncio
async def test_each_request_gets_a_unique_request_id():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r1 = await client.get("/health")
        r2 = await client.get("/health")

    assert r1.headers[REQUEST_ID_HEADER] != r2.headers[REQUEST_ID_HEADER]
