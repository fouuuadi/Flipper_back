import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import from_url

from app import di
from app.infrastructure.redis.session_store import SESSION_KEY_PREFIX
from app.main import app
from tests.conftest import make_db_pool, truncate_all

def _redis_url() -> str:
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    # En dehors de Docker, remplacer le hostname 'redis' par 'localhost'
    return url.replace("redis://redis:", "redis://localhost:")


REDIS_URL = _redis_url()



class _SessionServiceNoCollision:
    async def check_pseudo_uniqueness_in_room(self, room_code: str, pseudo: str) -> bool:
        return True


class _SessionServiceAlwaysCollide:
    async def check_pseudo_uniqueness_in_room(self, room_code: str, pseudo: str) -> bool:
        return False



@pytest_asyncio.fixture
async def db_pool():
    pool = await make_db_pool()
    di.set_db_pool(pool)
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def clean_tables(db_pool):
    await truncate_all(db_pool)
    yield


@pytest_asyncio.fixture
async def redis_client():
    client = from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await client.ping()
    di.set_redis_client(client)
    yield client
    async for key in client.scan_iter(match=f"{SESSION_KEY_PREFIX}*"):
        await client.delete(key)
    await client.aclose()


@pytest_asyncio.fixture
async def http_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()



async def _insert_player(db_pool, pseudo: str) -> int:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO players (pseudo) VALUES ($1) RETURNING id",
            pseudo,
        )
    return row["id"]


async def _post_matchmaking(http_client, player_id: int, mode: str = "1v1"):
    return await http_client.post(
        "/matchmaking", json={"player_id": player_id, "mode": mode}
    )



@pytest.mark.asyncio
async def test_matchmaking_pseudo_collision(db_pool, clean_tables, http_client):
    """Deux joueurs avec le même pseudo dans la même room → 409 Conflict."""
    app.dependency_overrides[di.get_session_service] = lambda: _SessionServiceAlwaysCollide()

    # Deux joueurs avec pseudos différents — c'est _SessionServiceAlwaysCollide
    # qui force la collision, peu importe les pseudos réels.
    p1 = await _insert_player(db_pool, "AAA#11111")
    p2 = await _insert_player(db_pool, "BBB#22222")

    r1 = await _post_matchmaking(http_client, p1)
    assert r1.status_code == 201
    assert r1.json()["status"] == "waiting"

    r2 = await _post_matchmaking(http_client, p2)
    assert r2.status_code == 409
    assert r2.json()["error"] == "PseudoCollisionInRoomError"


@pytest.mark.asyncio
async def test_matchmaking_pseudo_ok_different_pseudos(db_pool, clean_tables, http_client):
    """Pseudos différents → match créé normalement (201 matched)."""
    app.dependency_overrides[di.get_session_service] = lambda: _SessionServiceNoCollision()

    p1 = await _insert_player(db_pool, "AAA#11111")
    p2 = await _insert_player(db_pool, "BBB#22222")

    r1 = await _post_matchmaking(http_client, p1)
    assert r1.status_code == 201
    assert r1.json()["status"] == "waiting"

    r2 = await _post_matchmaking(http_client, p2)
    assert r2.status_code == 201
    body = r2.json()
    assert body["status"] == "matched"
    assert body["room_code"] is not None
    assert len(body["game_ids"]) == 2


@pytest.mark.asyncio
async def test_matchmaking_pseudo_ok_different_rooms(db_pool, clean_tables, redis_client, http_client):
    """Un pseudo déjà présent dans OLD_ROOM ne bloque pas un match dans une nouvelle room.

    On pré-insère une session Redis avec pseudo "AAA#11111" dans "OLD_ROOM".
    Le joueur p1 (pseudo "AAA#11111") fait un match contre p2 (pseudo "BBB#22222").
    Une nouvelle room est créée (≠ OLD_ROOM) → RedisSessionService ne détecte pas
    de collision car "AAA#11111" n'est pas actif dans la nouvelle room.
    """
    # Session active dans une room existante (OLD_ROOM) — ne doit pas bloquer
    await redis_client.hset(
        f"{SESSION_KEY_PREFIX}existing-session",
        mapping={
            "session_id": "existing-session",
            "pseudo": "AAA#11111",
            "score": "0",
            "lives": "3",
            "combo": "0",
            "status": "playing",
            "mode": "1v1",
            "room_code": "OLD_ROOM",
            "created_at": "2026-01-01T00:00:00",
        },
    )

    # Deux joueurs avec pseudos différents (contrainte unique DB)
    p1 = await _insert_player(db_pool, "AAA#11111")
    p2 = await _insert_player(db_pool, "BBB#22222")

    r1 = await _post_matchmaking(http_client, p1)
    assert r1.status_code == 201
    assert r1.json()["status"] == "waiting"

    r2 = await _post_matchmaking(http_client, p2)
    assert r2.status_code == 201
    body = r2.json()
    assert body["status"] == "matched"
    # La nouvelle room ≠ "OLD_ROOM" → pas de collision sur "AAA#11111"
    assert body["room_code"] != "OLD_ROOM"
    assert len(body["game_ids"]) == 2
