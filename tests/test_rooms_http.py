"""Tests d'intégration des routes HTTP /rooms (flux REST legacy rooms/games).

Création d'une room, jonction par code, et listing. Tournent contre une vraie
base Postgres (cf. fixtures conftest).
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import di
from app.main import app
from tests.conftest import make_db_pool, truncate_all


@pytest_asyncio.fixture
async def db_pool():
    pool = await make_db_pool()
    di.set_db_pool(pool)
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def clean(db_pool):
    await truncate_all(db_pool)
    yield


@pytest_asyncio.fixture
async def http_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def _create_room(http_client, mode: str = "solo") -> dict:
    resp = await http_client.post("/rooms", json={"mode": mode})
    assert resp.status_code == 201
    return resp.json()


# --- POST /rooms ------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_rooms_creates_waiting_room(db_pool, clean, http_client):
    body = await _create_room(http_client, "1v1")
    assert body["room_code"]
    assert body["mode"] == "1v1"
    assert body["status"] == "waiting"


# --- POST /rooms/{code}/join ------------------------------------------------


@pytest.mark.asyncio
async def test_post_join_room_returns_room(db_pool, clean, http_client):
    room = await _create_room(http_client)
    resp = await http_client.post(f"/rooms/{room['room_code']}/join")
    assert resp.status_code == 200
    body = resp.json()
    assert body["room_code"] == room["room_code"]
    assert body["games"] == []  # aucune partie démarrée dans cette room


@pytest.mark.asyncio
async def test_post_join_room_unknown_is_404(db_pool, clean, http_client):
    resp = await http_client.post("/rooms/ZZZZZZ/join")
    assert resp.status_code == 404
    assert resp.json()["error"] == "RoomNotFoundError"


# --- GET /rooms/list --------------------------------------------------------


@pytest.mark.asyncio
async def test_get_rooms_list_returns_created_rooms(db_pool, clean, http_client):
    await _create_room(http_client, "solo")
    await _create_room(http_client, "1v1")
    resp = await http_client.get("/rooms/list")
    assert resp.status_code == 200
    assert len(resp.json()["rooms"]) == 2


@pytest.mark.asyncio
async def test_get_rooms_list_filters_by_status(db_pool, clean, http_client):
    await _create_room(http_client)
    waiting = await http_client.get("/rooms/list", params={"status": "waiting"})
    playing = await http_client.get("/rooms/list", params={"status": "playing"})
    assert len(waiting.json()["rooms"]) == 1
    assert len(playing.json()["rooms"]) == 0
