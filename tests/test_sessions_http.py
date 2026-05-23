import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import from_url

from app import di
from app.infrastructure.redis.session_store import SESSION_KEY_PREFIX
from app.main import app

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@pytest_asyncio.fixture
async def redis_client():
    client = from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await client.ping()
    di.set_redis_client(client)
    yield client
    # Cleanup any keys produced by tests
    async for key in client.scan_iter(match=f"{SESSION_KEY_PREFIX}*"):
        await client.delete(key)
    await client.aclose()


@pytest_asyncio.fixture
async def http_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_create_session_applies_default_hashtag(redis_client, http_client):
    response = await http_client.post("/sessions", json={"pseudo": "abc"})

    assert response.status_code == 201
    body = response.json()
    assert "session_id" in body
    assert body["pseudo"] == "ABC#HETIC"
    assert body["status"] == "waiting"
    assert body["room_code"] is None

    # Session is in Redis
    stored = await redis_client.hgetall(SESSION_KEY_PREFIX + body["session_id"])
    assert stored["pseudo"] == body["pseudo"]
    assert stored["status"] == "waiting"


@pytest.mark.asyncio
async def test_create_session_keeps_explicit_hashtag(redis_client, http_client):
    response = await http_client.post("/sessions", json={"pseudo": "foo#bar12"})

    assert response.status_code == 201
    assert response.json()["pseudo"] == "FOO#BAR12"


@pytest.mark.asyncio
async def test_create_session_with_room_code(redis_client, http_client):
    response = await http_client.post(
        "/sessions", json={"pseudo": "xyz", "room_code": "ROOM01"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["room_code"] == "ROOM01"
    assert body["pseudo"] == "XYZ#HETIC"


@pytest.mark.parametrize(
    "bad_pseudo",
    ["AB", "ABCD", "abc#x", "abc#toolong", "abc-#hello", "###"],
)
@pytest.mark.asyncio
async def test_create_session_rejects_invalid_pseudo_format(
    redis_client, http_client, bad_pseudo
):
    response = await http_client.post("/sessions", json={"pseudo": bad_pseudo})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ready_up_marks_session_ready(redis_client, http_client):
    create_resp = await http_client.post("/sessions", json={"pseudo": "abc"})
    session_id = create_resp.json()["session_id"]

    ready_resp = await http_client.post(f"/sessions/{session_id}/ready")

    assert ready_resp.status_code == 200
    body = ready_resp.json()
    assert body["session_id"] == session_id
    assert body["status"] == "ready"

    stored = await redis_client.hgetall(SESSION_KEY_PREFIX + session_id)
    assert stored["status"] == "ready"


@pytest.mark.asyncio
async def test_ready_up_returns_404_for_unknown_session(redis_client, http_client):
    response = await http_client.post("/sessions/unknown-id/ready")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "SessionNotFoundError"
