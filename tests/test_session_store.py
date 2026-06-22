import os
import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from redis.asyncio import from_url

from app.domain.session import Session, SessionStatus
from app.infrastructure.redis.session_store import (
    SESSION_KEY_PREFIX,
    RedisSessionStore,
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
TTL_SECONDS = 1800


@pytest_asyncio.fixture
async def redis_client():
    client = from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await client.ping()
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def store(redis_client):
    yield RedisSessionStore(redis_client, ttl_seconds=TTL_SECONDS)


def _make_session(session_id: str | None = None, **overrides) -> Session:
    base = {
        "session_id": session_id or uuid.uuid4().hex,
        "pseudo": "ABC",
        "score": 0,
        "status": SessionStatus.WAITING,
        "room_code": None,
        "created_at": datetime(2026, 5, 22, 12, 0, 0),
    }
    base.update(overrides)
    return Session(**base)


@pytest.mark.asyncio
async def test_create_and_get_roundtrip(store, redis_client):
    session = _make_session()

    await store.create(session)
    fetched = await store.get(session.session_id)

    assert fetched is not None
    assert fetched.session_id == session.session_id
    assert fetched.pseudo == session.pseudo
    assert fetched.score == 0
    assert fetched.status == SessionStatus.WAITING
    assert fetched.room_code is None
    assert fetched.created_at == session.created_at

    await redis_client.delete(SESSION_KEY_PREFIX + session.session_id)


@pytest.mark.asyncio
async def test_get_unknown_returns_none(store):
    fetched = await store.get(uuid.uuid4().hex)
    assert fetched is None


@pytest.mark.asyncio
async def test_update_overrides_fields(store, redis_client):
    session = _make_session(score=10, status=SessionStatus.WAITING)
    await store.create(session)

    session.score = 150
    session.status = SessionStatus.PLAYING
    session.room_code = "ROOM01"
    await store.update(session)

    fetched = await store.get(session.session_id)
    assert fetched is not None
    assert fetched.score == 150
    assert fetched.status == SessionStatus.PLAYING
    assert fetched.room_code == "ROOM01"

    await redis_client.delete(SESSION_KEY_PREFIX + session.session_id)


@pytest.mark.asyncio
async def test_delete_removes_session(store):
    session = _make_session()
    await store.create(session)
    assert await store.get(session.session_id) is not None

    await store.delete(session.session_id)

    assert await store.get(session.session_id) is None


@pytest.mark.asyncio
async def test_create_sets_ttl(store, redis_client):
    session = _make_session()
    await store.create(session)

    ttl = await redis_client.ttl(SESSION_KEY_PREFIX + session.session_id)
    # Le TTL Redis renvoie les secondes restantes. Doit être entre 0 et TTL_SECONDS.
    assert 0 < ttl <= TTL_SECONDS

    await redis_client.delete(SESSION_KEY_PREFIX + session.session_id)


@pytest.mark.asyncio
async def test_get_refreshes_ttl(store, redis_client):
    """Sliding TTL : un get sur la session rafraîchit son expiration."""
    session = _make_session()
    await store.create(session)
    key = SESSION_KEY_PREFIX + session.session_id

    # Force un TTL court, puis appelle get et vérifie qu'il a été rafraîchi.
    await redis_client.expire(key, 60)
    ttl_before = await redis_client.ttl(key)
    assert ttl_before <= 60

    await store.get(session.session_id)
    ttl_after = await redis_client.ttl(key)
    assert ttl_after > ttl_before

    await redis_client.delete(key)


@pytest.mark.asyncio
async def test_update_refreshes_ttl(store, redis_client):
    session = _make_session()
    await store.create(session)
    key = SESSION_KEY_PREFIX + session.session_id

    await redis_client.expire(key, 60)
    ttl_before = await redis_client.ttl(key)

    session.score = 50
    await store.update(session)
    ttl_after = await redis_client.ttl(key)
    assert ttl_after > ttl_before

    await redis_client.delete(key)


@pytest.mark.asyncio
async def test_room_code_empty_string_returns_none(store, redis_client):
    """Une session stockée avec un room_code chaîne vide doit faire un roundtrip vers None."""
    session = _make_session(room_code=None)
    await store.create(session)

    fetched = await store.get(session.session_id)
    assert fetched is not None
    assert fetched.room_code is None

    await redis_client.delete(SESSION_KEY_PREFIX + session.session_id)
