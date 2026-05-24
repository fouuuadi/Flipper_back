import os
import uuid

import aiomysql
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from redis.asyncio import from_url

from app import di
from app.infrastructure.redis.event_buffer import EVENT_BUFFER_KEY_PREFIX
from app.infrastructure.redis.session_store import SESSION_KEY_PREFIX
from app.main import app

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@pytest_asyncio.fixture
async def redis_client():
    client = from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await client.ping()
    di.set_redis_client(client)
    yield client
    async for key in client.scan_iter(match=f"{SESSION_KEY_PREFIX}*"):
        await client.delete(key)
    async for key in client.scan_iter(match=f"{EVENT_BUFFER_KEY_PREFIX}*"):
        await client.delete(key)
    await client.aclose()


@pytest_asyncio.fixture
async def db_pool():
    host = os.getenv("DB_HOST", "localhost")
    if host == "db":
        host = "localhost"
    pool = await aiomysql.create_pool(
        host=host,
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "flipper"),
        password=os.getenv("DB_PASSWORD"),
        db=os.getenv("DB_NAME", "flipper"),
        minsize=1,
        maxsize=5,
        connect_timeout=10,
    )
    di.set_db_pool(pool)
    yield pool
    pool.close()
    await pool.wait_closed()


@pytest_asyncio.fixture
async def clean_tables(db_pool):
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            await cursor.execute("DELETE FROM game_events")
            await cursor.execute("DELETE FROM games")
            await cursor.execute("DELETE FROM rooms")
            await cursor.execute("DELETE FROM players")
            await cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            await conn.commit()
    yield


@pytest_asyncio.fixture
async def http_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_post_scores_flushes_session_end_to_end(
    redis_client, db_pool, clean_tables, http_client
):
    # Create session via HTTP
    create_resp = await http_client.post(
        "/sessions", json={"pseudo": "abc", "mode": "solo"}
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["session_id"]

    # Seed an event in Redis (as if HandleMqttEventUseCase had pushed)
    key = EVENT_BUFFER_KEY_PREFIX + session_id
    import json
    await redis_client.rpush(
        key,
        json.dumps({
            "topic": "flipper/bumper/hit",
            "payload": {"points": 75, "bumperId": 2},
            "occured_at": "2026-05-23T10:00:01+00:00",
        }),
    )

    # Flush
    resp = await http_client.post("/scores", json={"sessionId": session_id})

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["eventCount"] == 1
    assert body["playerId"] > 0
    assert body["gameId"] > 0
    # First solo flush ever for this pseudo: improved=true, previousBest=null.
    assert body["improved"] is True
    assert body["previousBest"] is None

    # Redis fully cleaned
    assert await redis_client.exists(SESSION_KEY_PREFIX + session_id) == 0
    assert await redis_client.exists(EVENT_BUFFER_KEY_PREFIX + session_id) == 0

    # Player + Game persisted
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT pseudo FROM players WHERE id = %s", (body["playerId"],))
            assert (await cursor.fetchone())["pseudo"].startswith("ABC#")

            await cursor.execute("SELECT mode, score FROM games WHERE id = %s", (body["gameId"],))
            game = await cursor.fetchone()
            assert game["mode"] == "solo"


@pytest.mark.asyncio
async def test_post_scores_unknown_session_returns_404(redis_client, db_pool, clean_tables, http_client):
    fake_id = uuid.uuid4().hex
    resp = await http_client.post("/scores", json={"sessionId": fake_id})
    assert resp.status_code == 404
    assert resp.json()["error"] == "SessionNotFoundError"


async def _flush_session(http_client, pseudo: str, mode: str, score: int) -> dict:
    """Helper that creates a session, forces its score in Redis, then flushes it."""
    create_resp = await http_client.post("/sessions", json={"pseudo": pseudo, "mode": mode})
    session_id = create_resp.json()["session_id"]
    # Inject the score directly in the Redis Hash without going through MQTT.
    from app import di as app_di
    redis = app_di._redis_client
    await redis.hset(f"session:{session_id}", "score", str(score))
    return (await http_client.post("/scores", json={"sessionId": session_id})).json()


@pytest.mark.asyncio
async def test_post_scores_solo_improved_flag_progression(
    redis_client, db_pool, clean_tables, http_client
):
    # 1st solo run — first ever, improved=true, previousBest=null.
    r1 = await _flush_session(http_client, "abc", "solo", 1200)
    assert r1["improved"] is True
    assert r1["previousBest"] is None

    # 2nd run, higher score → improved=true, previousBest=1200.
    r2 = await _flush_session(http_client, "abc", "solo", 4500)
    assert r2["improved"] is True
    assert r2["previousBest"] == 1200

    # 3rd run, lower score → improved=false, previousBest=4500.
    r3 = await _flush_session(http_client, "abc", "solo", 800)
    assert r3["improved"] is False
    assert r3["previousBest"] == 4500


@pytest.mark.asyncio
async def test_post_scores_one_v_one_returns_null_improved(
    redis_client, db_pool, clean_tables, http_client
):
    body = await _flush_session(http_client, "abc", "1v1", 3000)
    assert body["improved"] is None
    assert body["previousBest"] is None
