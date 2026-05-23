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
async def clean_players(db_pool):
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            await cursor.execute("DELETE FROM game_events")
            await cursor.execute("DELETE FROM games")
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
async def test_post_players_creates_then_returns_same_player(db_pool, clean_players, http_client):
    first = await http_client.post("/players", json={"pseudo": "abc"})
    assert first.status_code == 200
    body1 = first.json()
    assert body1["pseudo"] == "ABC#HETIC"
    assert body1["id"] > 0

    # Idempotent: a second POST with the same pseudo returns the same row.
    second = await http_client.post("/players", json={"pseudo": "ABC"})
    assert second.status_code == 200
    body2 = second.json()
    assert body2["id"] == body1["id"]
    assert body2["created_at"] == body1["created_at"]


@pytest.mark.asyncio
async def test_post_players_distinguishes_hashtags(db_pool, clean_players, http_client):
    r1 = await http_client.post("/players", json={"pseudo": "abc#alpha"})
    r2 = await http_client.post("/players", json={"pseudo": "abc#beta1"})
    assert r1.json()["id"] != r2.json()["id"]


@pytest.mark.parametrize("bad_pseudo", ["AB", "ABCD", "abc#x", "abc#toolong", "abc-x"])
@pytest.mark.asyncio
async def test_post_players_rejects_invalid_format(db_pool, clean_players, http_client, bad_pseudo):
    response = await http_client.post("/players", json={"pseudo": bad_pseudo})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_player_by_id_returns_player(db_pool, clean_players, http_client):
    created = await http_client.post("/players", json={"pseudo": "xyz#alpha"})
    player_id = created.json()["id"]

    response = await http_client.get(f"/players/{player_id}")

    assert response.status_code == 200
    assert response.json()["pseudo"] == "XYZ#ALPHA"


@pytest.mark.asyncio
async def test_get_player_by_id_returns_404_when_missing(db_pool, clean_players, http_client):
    response = await http_client.get("/players/999999")
    assert response.status_code == 404
    assert response.json()["error"] == "PlayerNotFoundError"


@pytest.mark.asyncio
async def test_get_player_by_pseudo_query_param(db_pool, clean_players, http_client):
    await http_client.post("/players", json={"pseudo": "foo#bar12"})

    found = await http_client.get("/players", params={"pseudo": "foo#bar12"})
    assert found.status_code == 200
    assert found.json()["pseudo"] == "FOO#BAR12"

    missing = await http_client.get("/players", params={"pseudo": "xyz#nope1"})
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_get_player_by_pseudo_invalid_format_returns_422(db_pool, clean_players, http_client):
    response = await http_client.get("/players", params={"pseudo": "AB"})
    assert response.status_code == 422
    assert response.json()["error"] == "InvalidPseudoError"
