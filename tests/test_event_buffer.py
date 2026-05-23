import os
import uuid

import pytest
import pytest_asyncio
from redis.asyncio import from_url

from app.infrastructure.redis.event_buffer import EVENT_BUFFER_KEY_PREFIX, RedisEventBuffer

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
TTL_SECONDS = 1800


@pytest_asyncio.fixture
async def redis_client():
    client = from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await client.ping()
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def buffer(redis_client):
    yield RedisEventBuffer(redis_client, ttl_seconds=TTL_SECONDS)


@pytest.mark.asyncio
async def test_push_and_read_returns_events_in_order(buffer, redis_client):
    session_id = uuid.uuid4().hex

    await buffer.push(session_id, {"topic": "flipper/bumper/hit", "payload": {"points": 10}})
    await buffer.push(session_id, {"topic": "flipper/ball/lost", "payload": {}})
    await buffer.push(session_id, {"topic": "flipper/game/over", "payload": {}})

    events = await buffer.read_all(session_id)
    assert [e["topic"] for e in events] == [
        "flipper/bumper/hit",
        "flipper/ball/lost",
        "flipper/game/over",
    ]
    assert events[0]["payload"] == {"points": 10}

    await redis_client.delete(EVENT_BUFFER_KEY_PREFIX + session_id)


@pytest.mark.asyncio
async def test_read_unknown_session_returns_empty(buffer):
    assert await buffer.read_all(uuid.uuid4().hex) == []


@pytest.mark.asyncio
async def test_clear_removes_all_events(buffer):
    session_id = uuid.uuid4().hex
    await buffer.push(session_id, {"topic": "flipper/bumper/hit", "payload": {}})
    await buffer.push(session_id, {"topic": "flipper/ball/lost", "payload": {}})

    await buffer.clear(session_id)

    assert await buffer.read_all(session_id) == []


@pytest.mark.asyncio
async def test_push_sets_sliding_ttl(buffer, redis_client):
    session_id = uuid.uuid4().hex
    await buffer.push(session_id, {"topic": "test", "payload": {}})

    key = EVENT_BUFFER_KEY_PREFIX + session_id
    ttl = await redis_client.ttl(key)
    assert 0 < ttl <= TTL_SECONDS

    await redis_client.delete(key)
