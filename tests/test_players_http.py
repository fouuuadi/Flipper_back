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
async def test_player_history_returns_games_desc(db_pool, clean_players, http_client):
    created = await http_client.post("/players", json={"pseudo": "abc"})
    player_id = created.json()["id"]
    g1 = await _insert_finished_game(db_pool, player_id, "solo", 100)
    g2 = await _insert_finished_game(db_pool, player_id, "solo", 200)
    g3 = await _insert_finished_game(db_pool, player_id, "1v1", 300)

    response = await http_client.get(f"/players/{player_id}/games")

    assert response.status_code == 200
    body = response.json()
    assert body["player_id"] == player_id
    assert body["pseudo"] == "ABC#HETIC"
    # Most recent first (g3, g2, g1) — same NOW() but ORDER BY id DESC tie-break.
    assert [g["game_id"] for g in body["games"]] == [g3, g2, g1]
    assert all(g["finished_at"] for g in body["games"])
    assert all(g["started_at"] for g in body["games"])


@pytest.mark.asyncio
async def test_player_history_filters_by_mode(db_pool, clean_players, http_client):
    created = await http_client.post("/players", json={"pseudo": "abc"})
    player_id = created.json()["id"]
    await _insert_finished_game(db_pool, player_id, "solo", 100)
    g_1v1 = await _insert_finished_game(db_pool, player_id, "1v1", 200)

    response = await http_client.get(f"/players/{player_id}/games", params={"mode": "1v1"})

    body = response.json()
    assert [g["game_id"] for g in body["games"]] == [g_1v1]


@pytest.mark.asyncio
async def test_player_history_respects_limit(db_pool, clean_players, http_client):
    created = await http_client.post("/players", json={"pseudo": "abc"})
    player_id = created.json()["id"]
    for score in (10, 20, 30, 40, 50):
        await _insert_finished_game(db_pool, player_id, "solo", score)

    response = await http_client.get(f"/players/{player_id}/games", params={"limit": 2})

    body = response.json()
    assert len(body["games"]) == 2


@pytest.mark.asyncio
async def test_player_history_ignores_non_finished_games(db_pool, clean_players, http_client):
    created = await http_client.post("/players", json={"pseudo": "abc"})
    player_id = created.json()["id"]
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO games (player_id, room_id, mode, score, status) "
                "VALUES (%s, NULL, 'solo', 999, 'playing')",
                (player_id,),
            )
            await conn.commit()

    response = await http_client.get(f"/players/{player_id}/games")
    assert response.json()["games"] == []


@pytest.mark.asyncio
async def test_player_history_empty_when_no_games(db_pool, clean_players, http_client):
    created = await http_client.post("/players", json={"pseudo": "abc"})
    player_id = created.json()["id"]

    response = await http_client.get(f"/players/{player_id}/games")
    assert response.status_code == 200
    assert response.json()["games"] == []


@pytest.mark.asyncio
async def test_player_history_unknown_player_returns_404(db_pool, clean_players, http_client):
    response = await http_client.get("/players/999999/games")
    assert response.status_code == 404
    assert response.json()["error"] == "PlayerNotFoundError"


@pytest.mark.parametrize("bad_limit", [0, -1, 101, 9999])
@pytest.mark.asyncio
async def test_player_history_rejects_invalid_limit(db_pool, clean_players, http_client, bad_limit):
    created = await http_client.post("/players", json={"pseudo": "abc"})
    player_id = created.json()["id"]

    response = await http_client.get(f"/players/{player_id}/games", params={"limit": bad_limit})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_player_history_rejects_unknown_mode(db_pool, clean_players, http_client):
    created = await http_client.post("/players", json={"pseudo": "abc"})
    player_id = created.json()["id"]

    response = await http_client.get(
        f"/players/{player_id}/games", params={"mode": "battle-royale"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_player_history_marks_best_solo_game(db_pool, clean_players, http_client):
    created = await http_client.post("/players", json={"pseudo": "abc"})
    player_id = created.json()["id"]
    g_low = await _insert_finished_game(db_pool, player_id, "solo", 1200)
    g_best = await _insert_finished_game(db_pool, player_id, "solo", 4500)
    g_mid = await _insert_finished_game(db_pool, player_id, "solo", 800)

    response = await http_client.get(f"/players/{player_id}/games", params={"mode": "solo"})

    body = response.json()
    flags = {g["game_id"]: g["is_best"] for g in body["games"]}
    assert flags == {g_best: True, g_low: False, g_mid: False}


@pytest.mark.asyncio
async def test_player_history_never_marks_1v1_as_best(db_pool, clean_players, http_client):
    created = await http_client.post("/players", json={"pseudo": "abc"})
    player_id = created.json()["id"]
    await _insert_finished_game(db_pool, player_id, "1v1", 5000)
    await _insert_finished_game(db_pool, player_id, "1v1", 3000)

    response = await http_client.get(f"/players/{player_id}/games", params={"mode": "1v1"})

    body = response.json()
    assert all(g["is_best"] is False for g in body["games"])
