import os

import aiomysql
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient

from app import di
from app.main import app

load_dotenv()


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


async def _insert_player(db_pool, pseudo: str) -> int:
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("INSERT INTO players (pseudo) VALUES (%s)", (pseudo,))
            await conn.commit()
            return cursor.lastrowid


async def _insert_finished_game(db_pool, player_id: int, mode: str, score: int) -> int:
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO games (player_id, room_id, mode, score, status, finished_at) "
                "VALUES (%s, NULL, %s, %s, 'finished', NOW())",
                (player_id, mode, score),
            )
            await conn.commit()
            return cursor.lastrowid


@pytest.mark.asyncio
async def test_leaderboard_returns_top_scores_ordered_desc(db_pool, clean_tables, http_client):
    p1 = await _insert_player(db_pool, "AAA#HETIC")
    p2 = await _insert_player(db_pool, "BBB#HETIC")
    p3 = await _insert_player(db_pool, "CCC#HETIC")
    await _insert_finished_game(db_pool, p1, "solo", 1000)
    await _insert_finished_game(db_pool, p1, "solo", 4200)  # p1 best = 4200
    await _insert_finished_game(db_pool, p2, "solo", 2500)
    await _insert_finished_game(db_pool, p3, "solo", 3000)

    response = await http_client.get("/leaderboard", params={"mode": "solo"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "solo"
    assert body["limit"] == 10
    entries = body["entries"]
    assert [e["rank"] for e in entries] == [1, 2, 3]
    assert [e["score"] for e in entries] == [4200, 3000, 2500]
    assert [e["player_id"] for e in entries] == [p1, p3, p2]


@pytest.mark.asyncio
async def test_leaderboard_filters_by_mode(db_pool, clean_tables, http_client):
    p1 = await _insert_player(db_pool, "AAA#HETIC")
    p2 = await _insert_player(db_pool, "BBB#HETIC")
    await _insert_finished_game(db_pool, p1, "solo", 5000)
    await _insert_finished_game(db_pool, p2, "1v1", 9000)

    solo = (await http_client.get("/leaderboard", params={"mode": "solo"})).json()
    one_v_one = (await http_client.get("/leaderboard", params={"mode": "1v1"})).json()

    assert [e["player_id"] for e in solo["entries"]] == [p1]
    assert [e["player_id"] for e in one_v_one["entries"]] == [p2]


@pytest.mark.asyncio
async def test_leaderboard_without_mode_aggregates_all_modes(db_pool, clean_tables, http_client):
    p1 = await _insert_player(db_pool, "AAA#HETIC")
    p2 = await _insert_player(db_pool, "BBB#HETIC")
    await _insert_finished_game(db_pool, p1, "solo", 100)
    await _insert_finished_game(db_pool, p1, "1v1", 8000)  # p1 max across modes
    await _insert_finished_game(db_pool, p2, "solo", 3000)

    response = await http_client.get("/leaderboard")

    body = response.json()
    assert body["mode"] is None
    assert [e["score"] for e in body["entries"]] == [8000, 3000]


@pytest.mark.asyncio
async def test_leaderboard_respects_limit(db_pool, clean_tables, http_client):
    for i in range(5):
        pid = await _insert_player(db_pool, f"P{i:02d}#HETIC")
        await _insert_finished_game(db_pool, pid, "solo", 100 * (i + 1))

    response = await http_client.get("/leaderboard", params={"mode": "solo", "limit": 3})

    body = response.json()
    assert body["limit"] == 3
    assert len(body["entries"]) == 3
    assert [e["score"] for e in body["entries"]] == [500, 400, 300]


@pytest.mark.asyncio
async def test_leaderboard_ignores_non_finished_games(db_pool, clean_tables, http_client):
    p1 = await _insert_player(db_pool, "AAA#HETIC")
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO games (player_id, room_id, mode, score, status) "
                "VALUES (%s, NULL, 'solo', 9999, 'playing')",
                (p1,),
            )
            await conn.commit()

    response = await http_client.get("/leaderboard", params={"mode": "solo"})
    assert response.json()["entries"] == []


@pytest.mark.asyncio
async def test_leaderboard_empty_when_no_games(db_pool, clean_tables, http_client):
    response = await http_client.get("/leaderboard", params={"mode": "solo"})
    body = response.json()
    assert body["entries"] == []


@pytest.mark.parametrize("bad_limit", [0, -1, 101, 9999])
@pytest.mark.asyncio
async def test_leaderboard_rejects_invalid_limit(db_pool, clean_tables, http_client, bad_limit):
    response = await http_client.get("/leaderboard", params={"limit": bad_limit})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_leaderboard_rejects_unknown_mode(db_pool, clean_tables, http_client):
    response = await http_client.get("/leaderboard", params={"mode": "battle-royale"})
    assert response.status_code == 422
