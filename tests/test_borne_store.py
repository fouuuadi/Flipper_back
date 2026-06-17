import os
import uuid

import pytest
import pytest_asyncio
from redis.asyncio import from_url

from app.domain.borne import BorneNavState
from app.infrastructure.redis.borne_store import BORNE_KEY_PREFIX, RedisBorneStore

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@pytest_asyncio.fixture
async def redis_client():
    client = from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await client.ping()
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def store(redis_client):
    yield RedisBorneStore(redis_client)


@pytest.mark.asyncio
async def test_get_or_create_creates_splash_when_absent(store, redis_client):
    borne_id = f"borne-{uuid.uuid4().hex}"

    borne = await store.get_or_create(borne_id)

    assert borne.borne_id == borne_id
    assert borne.nav == BorneNavState.SPLASH
    assert borne.active_session_id is None
    assert await redis_client.exists(BORNE_KEY_PREFIX + borne_id) == 1

    await redis_client.delete(BORNE_KEY_PREFIX + borne_id)


@pytest.mark.asyncio
async def test_get_or_create_returns_existing(store, redis_client):
    borne_id = f"borne-{uuid.uuid4().hex}"
    borne = await store.get_or_create(borne_id)
    borne.nav = BorneNavState.MENU
    borne.active_session_id = "sess-123"
    await store.update(borne)

    again = await store.get_or_create(borne_id)

    assert again.nav == BorneNavState.MENU
    assert again.active_session_id == "sess-123"

    await redis_client.delete(BORNE_KEY_PREFIX + borne_id)


@pytest.mark.asyncio
async def test_update_roundtrip(store, redis_client):
    borne_id = f"borne-{uuid.uuid4().hex}"
    borne = await store.get_or_create(borne_id)

    borne.nav = BorneNavState.IN_GAME
    borne.active_session_id = "sess-xyz"
    await store.update(borne)

    fetched = await store.get_or_create(borne_id)
    assert fetched.nav == BorneNavState.IN_GAME
    assert fetched.active_session_id == "sess-xyz"

    await redis_client.delete(BORNE_KEY_PREFIX + borne_id)


@pytest.mark.asyncio
async def test_empty_active_session_id_roundtrips_to_none(store, redis_client):
    borne_id = f"borne-{uuid.uuid4().hex}"
    borne = await store.get_or_create(borne_id)
    borne.nav = BorneNavState.MENU
    borne.active_session_id = None
    await store.update(borne)

    fetched = await store.get_or_create(borne_id)
    assert fetched.active_session_id is None

    await redis_client.delete(BORNE_KEY_PREFIX + borne_id)


@pytest.mark.asyncio
async def test_borne_has_no_ttl(store, redis_client):
    """La borne est permanente : aucune expiration ne doit être posée."""
    borne_id = f"borne-{uuid.uuid4().hex}"
    await store.get_or_create(borne_id)

    # -1 = clé sans TTL (persistante) en Redis.
    assert await redis_client.ttl(BORNE_KEY_PREFIX + borne_id) == -1

    await redis_client.delete(BORNE_KEY_PREFIX + borne_id)
