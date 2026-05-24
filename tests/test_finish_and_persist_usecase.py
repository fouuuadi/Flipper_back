import os
import uuid
from datetime import datetime, timezone

import aiomysql
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from redis.asyncio import from_url

from app.domain.exceptions import SessionNotFoundError
from app.domain.game import GameMode
from app.domain.session import Session, SessionStatus
from app.infrastructure.db.game_repository import MysqlGameRepository
from app.infrastructure.db.player_repository import MysqlPlayerRepository
from app.infrastructure.redis.event_buffer import EVENT_BUFFER_KEY_PREFIX, RedisEventBuffer
from app.infrastructure.redis.session_store import SESSION_KEY_PREFIX, RedisSessionStore
from app.usecase.finish_and_persist_usecase import FinishAndPersistUseCase

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
TTL_SECONDS = 1800


@pytest_asyncio.fixture
async def redis_client():
    client = from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await client.ping()
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def session_store(redis_client):
    return RedisSessionStore(redis_client, ttl_seconds=TTL_SECONDS)


@pytest_asyncio.fixture
async def event_buffer(redis_client):
    return RedisEventBuffer(redis_client, ttl_seconds=TTL_SECONDS)


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
    yield pool
    pool.close()
    await pool.wait_closed()


@pytest_asyncio.fixture
async def game_repo(db_pool):
    return MysqlGameRepository(db_pool)


@pytest_asyncio.fixture
async def player_repo(db_pool):
    return MysqlPlayerRepository(db_pool)


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


def _build_session(session_id: str, score: int = 0, mode: GameMode = GameMode.SOLO) -> Session:
    return Session(
        session_id=session_id,
        pseudo=f"TST#{session_id[:4]}",
        score=score,
        lives=2,
        combo=4,
        status=SessionStatus.OVER,
        mode=mode,
        room_code=None,
        created_at=datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_flush_persists_player_game_and_events(
    session_store, event_buffer, game_repo, player_repo, clean_tables, redis_client, db_pool
):
    session_id = uuid.uuid4().hex
    session = _build_session(session_id, score=4200)
    await session_store.create(session)
    await event_buffer.push(
        session_id,
        {
            "topic": "flipper/bumper/hit",
            "payload": {"bumperId": 1, "points": 100},
            "occured_at": "2026-05-23T10:00:01+00:00",
        },
    )
    await event_buffer.push(
        session_id,
        {
            "topic": "flipper/game/over",
            "payload": {},
            "occured_at": "2026-05-23T10:00:02+00:00",
        },
    )

    usecase = FinishAndPersistUseCase(session_store, event_buffer, game_repo, player_repo)
    result = await usecase.execute(session_id)

    assert result.final_score == 4200
    assert result.event_count == 2
    assert result.player_id > 0
    assert result.game_id > 0

    # Redis cleaned up
    assert await redis_client.exists(SESSION_KEY_PREFIX + session_id) == 0
    assert await redis_client.exists(EVENT_BUFFER_KEY_PREFIX + session_id) == 0

    # DB has the expected rows
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT * FROM games WHERE id = %s", (result.game_id,))
            game_row = await cursor.fetchone()
            assert game_row["score"] == 4200
            assert game_row["mode"] == "solo"
            assert game_row["status"] == "finished"
            assert game_row["finished_at"] is not None

            await cursor.execute(
                "SELECT type, points FROM game_events WHERE game_id = %s ORDER BY id ASC",
                (result.game_id,),
            )
            event_rows = await cursor.fetchall()
            assert [r["type"] for r in event_rows] == ["bumper_hit", "game_over"]
            assert event_rows[0]["points"] == 100


@pytest.mark.asyncio
async def test_flush_reuses_existing_player(
    session_store, event_buffer, game_repo, player_repo, clean_tables, db_pool
):
    # Seed the same pseudo on two consecutive sessions.
    pseudo = "REU#0001"
    session_id_1 = uuid.uuid4().hex
    s1 = _build_session(session_id_1, score=100)
    s1.pseudo = pseudo
    await session_store.create(s1)

    result_1 = await FinishAndPersistUseCase(session_store, event_buffer, game_repo, player_repo).execute(session_id_1)

    session_id_2 = uuid.uuid4().hex
    s2 = _build_session(session_id_2, score=250)
    s2.pseudo = pseudo
    await session_store.create(s2)

    result_2 = await FinishAndPersistUseCase(session_store, event_buffer, game_repo, player_repo).execute(session_id_2)

    assert result_1.player_id == result_2.player_id
    assert result_1.game_id != result_2.game_id

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT COUNT(*) AS c FROM players WHERE pseudo = %s", (pseudo,))
            assert (await cursor.fetchone())["c"] == 1


@pytest.mark.asyncio
async def test_flush_with_no_events_still_creates_game(
    session_store, event_buffer, game_repo, player_repo, clean_tables, db_pool
):
    session_id = uuid.uuid4().hex
    await session_store.create(_build_session(session_id, score=42))

    result = await FinishAndPersistUseCase(session_store, event_buffer, game_repo, player_repo).execute(session_id)

    assert result.event_count == 0
    assert result.final_score == 42

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                "SELECT COUNT(*) AS c FROM game_events WHERE game_id = %s",
                (result.game_id,),
            )
            assert (await cursor.fetchone())["c"] == 0


@pytest.mark.asyncio
async def test_flush_unknown_session_raises(session_store, event_buffer, game_repo, player_repo, clean_tables):
    with pytest.raises(SessionNotFoundError):
        await FinishAndPersistUseCase(session_store, event_buffer, game_repo, player_repo).execute("ghost-id")


@pytest.mark.asyncio
async def test_unknown_event_topics_are_skipped(
    session_store, event_buffer, game_repo, player_repo, clean_tables, db_pool
):
    session_id = uuid.uuid4().hex
    await session_store.create(_build_session(session_id))
    await event_buffer.push(
        session_id,
        {"topic": "flipper/garbage", "payload": {}, "occured_at": "2026-05-23T10:00:01+00:00"},
    )
    await event_buffer.push(
        session_id,
        {"topic": "flipper/bumper/hit", "payload": {"points": 5}, "occured_at": "2026-05-23T10:00:02+00:00"},
    )

    result = await FinishAndPersistUseCase(session_store, event_buffer, game_repo, player_repo).execute(session_id)

    assert result.event_count == 1
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                "SELECT type FROM game_events WHERE game_id = %s",
                (result.game_id,),
            )
            rows = await cursor.fetchall()
            assert [r["type"] for r in rows] == ["bumper_hit"]


@pytest.mark.asyncio
async def test_first_solo_flush_marks_improved_true_with_null_previous_best(
    session_store, event_buffer, game_repo, player_repo, clean_tables
):
    session_id = uuid.uuid4().hex
    await session_store.create(_build_session(session_id, score=1200, mode=GameMode.SOLO))

    result = await FinishAndPersistUseCase(
        session_store, event_buffer, game_repo, player_repo
    ).execute(session_id)

    assert result.improved is True
    assert result.previous_best is None


@pytest.mark.asyncio
async def test_second_solo_flush_with_higher_score_marks_improved_true(
    session_store, event_buffer, game_repo, player_repo, clean_tables
):
    pseudo = "BST#HETIC"
    s1_id = uuid.uuid4().hex
    s1 = _build_session(s1_id, score=1000, mode=GameMode.SOLO)
    s1.pseudo = pseudo
    await session_store.create(s1)
    await FinishAndPersistUseCase(session_store, event_buffer, game_repo, player_repo).execute(s1_id)

    s2_id = uuid.uuid4().hex
    s2 = _build_session(s2_id, score=4500, mode=GameMode.SOLO)
    s2.pseudo = pseudo
    await session_store.create(s2)

    result = await FinishAndPersistUseCase(
        session_store, event_buffer, game_repo, player_repo
    ).execute(s2_id)

    assert result.improved is True
    assert result.previous_best == 1000


@pytest.mark.asyncio
async def test_solo_flush_with_lower_score_marks_improved_false(
    session_store, event_buffer, game_repo, player_repo, clean_tables
):
    pseudo = "WRS#HETIC"
    s1_id = uuid.uuid4().hex
    s1 = _build_session(s1_id, score=4500, mode=GameMode.SOLO)
    s1.pseudo = pseudo
    await session_store.create(s1)
    await FinishAndPersistUseCase(session_store, event_buffer, game_repo, player_repo).execute(s1_id)

    s2_id = uuid.uuid4().hex
    s2 = _build_session(s2_id, score=800, mode=GameMode.SOLO)
    s2.pseudo = pseudo
    await session_store.create(s2)

    result = await FinishAndPersistUseCase(
        session_store, event_buffer, game_repo, player_repo
    ).execute(s2_id)

    assert result.improved is False
    assert result.previous_best == 4500


@pytest.mark.asyncio
async def test_solo_flush_with_equal_score_marks_improved_false(
    session_store, event_buffer, game_repo, player_repo, clean_tables
):
    pseudo = "EQS#HETIC"
    s1_id = uuid.uuid4().hex
    s1 = _build_session(s1_id, score=2500, mode=GameMode.SOLO)
    s1.pseudo = pseudo
    await session_store.create(s1)
    await FinishAndPersistUseCase(session_store, event_buffer, game_repo, player_repo).execute(s1_id)

    s2_id = uuid.uuid4().hex
    s2 = _build_session(s2_id, score=2500, mode=GameMode.SOLO)
    s2.pseudo = pseudo
    await session_store.create(s2)

    result = await FinishAndPersistUseCase(
        session_store, event_buffer, game_repo, player_repo
    ).execute(s2_id)

    # Equal score does not beat the record → not "improved".
    assert result.improved is False
    assert result.previous_best == 2500


@pytest.mark.asyncio
async def test_one_v_one_flush_returns_improved_none(
    session_store, event_buffer, game_repo, player_repo, clean_tables
):
    session_id = uuid.uuid4().hex
    await session_store.create(_build_session(session_id, score=3000, mode=GameMode.ONE_V_ONE))

    result = await FinishAndPersistUseCase(
        session_store, event_buffer, game_repo, player_repo
    ).execute(session_id)

    assert result.improved is None
    assert result.previous_best is None


@pytest.mark.asyncio
async def test_one_v_one_flush_after_solo_does_not_use_solo_best_as_previous(
    session_store, event_buffer, game_repo, player_repo, clean_tables
):
    pseudo = "MIX#HETIC"
    # Seed a strong solo score first.
    s1_id = uuid.uuid4().hex
    s1 = _build_session(s1_id, score=8000, mode=GameMode.SOLO)
    s1.pseudo = pseudo
    await session_store.create(s1)
    await FinishAndPersistUseCase(session_store, event_buffer, game_repo, player_repo).execute(s1_id)

    # Now a 1v1 game with a lower score — should be flagged improved=None, not False.
    s2_id = uuid.uuid4().hex
    s2 = _build_session(s2_id, score=200, mode=GameMode.ONE_V_ONE)
    s2.pseudo = pseudo
    await session_store.create(s2)

    result = await FinishAndPersistUseCase(
        session_store, event_buffer, game_repo, player_repo
    ).execute(s2_id)

    assert result.improved is None
    assert result.previous_best is None
