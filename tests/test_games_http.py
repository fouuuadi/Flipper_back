"""Tests d'intégration des routes HTTP /games (flux REST legacy rooms/games).

Couvrent le cycle de vie d'une partie de bout en bout : démarrage, ajout d'events,
fin, lecture d'état, état d'une room et listing. Tournent contre une vraie base
Postgres (cf. fixtures conftest), au plus près de ce que voit un vrai client.
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


async def _start_game(http_client, pseudo: str = "abc", mode: str = "solo") -> dict:
    resp = await http_client.post(
        "/games/start", json={"pseudo": pseudo, "mode": mode}
    )
    assert resp.status_code == 201
    return resp.json()


# --- POST /games/start ------------------------------------------------------


@pytest.mark.asyncio
async def test_post_games_start_solo_returns_ids(db_pool, clean, http_client):
    body = await _start_game(http_client, "abc", "solo")
    assert body["game_id"] > 0
    assert body["player_id"] > 0
    assert body["event_id"] > 0
    assert body["room_code"]  # une room est toujours créée, même en solo


@pytest.mark.asyncio
async def test_post_games_start_reuses_existing_room(db_pool, clean, http_client):
    # Une première partie crée la room ; une seconde rejoint la même via son code.
    first = await _start_game(http_client, "abc", "1v1")
    resp = await http_client.post(
        "/games/start",
        json={"pseudo": "xyz", "mode": "1v1", "room_code": first["room_code"]},
    )
    assert resp.status_code == 201
    assert resp.json()["room_code"] == first["room_code"]


# --- POST /games/{id}/events ------------------------------------------------


@pytest.mark.asyncio
async def test_post_game_events_accumulates_score(db_pool, clean, http_client):
    game = await _start_game(http_client)
    resp = await http_client.post(
        f"/games/{game['game_id']}/events",
        json={"type": "bumper_hit", "points": 150},
    )
    assert resp.status_code == 201
    assert resp.json()["new_score"] == 150


@pytest.mark.asyncio
async def test_post_game_events_unknown_game_is_404(db_pool, clean, http_client):
    resp = await http_client.post(
        "/games/999999/events", json={"type": "bumper_hit", "points": 10}
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "GameNotFoundError"


# --- POST /games/{id}/finish ------------------------------------------------


@pytest.mark.asyncio
async def test_post_game_finish_marks_finished(db_pool, clean, http_client):
    game = await _start_game(http_client)
    resp = await http_client.post(f"/games/{game['game_id']}/finish")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "finished"
    assert body["finished_at"] is not None


# --- GET /games/{id} --------------------------------------------------------


@pytest.mark.asyncio
async def test_get_game_state_returns_events(db_pool, clean, http_client):
    game = await _start_game(http_client)
    await http_client.post(
        f"/games/{game['game_id']}/events",
        json={"type": "bumper_hit", "points": 50},
    )
    resp = await http_client.get(f"/games/{game['game_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 50
    # game_started (au démarrage) + bumper_hit ajouté ci-dessus.
    assert len(body["events"]) >= 2


@pytest.mark.asyncio
async def test_get_game_state_unknown_is_404(db_pool, clean, http_client):
    resp = await http_client.get("/games/999999")
    assert resp.status_code == 404
    assert resp.json()["error"] == "GameNotFoundError"


# --- GET /games/rooms/{code}/state ------------------------------------------


@pytest.mark.asyncio
async def test_get_room_state_returns_active_game(db_pool, clean, http_client):
    game = await _start_game(http_client)
    resp = await http_client.get(f"/games/rooms/{game['room_code']}/state")
    assert resp.status_code == 200
    body = resp.json()
    assert body["room_code"] == game["room_code"]
    assert any(g["game_id"] == game["game_id"] for g in body["games"])


@pytest.mark.asyncio
async def test_get_room_state_unknown_is_404(db_pool, clean, http_client):
    resp = await http_client.get("/games/rooms/ZZZZZZ/state")
    assert resp.status_code == 404
    assert resp.json()["error"] == "RoomNotFoundError"


# --- GET /games/list --------------------------------------------------------


@pytest.mark.asyncio
async def test_get_games_list_returns_started_games(db_pool, clean, http_client):
    await _start_game(http_client, "abc")
    await _start_game(http_client, "xyz")
    resp = await http_client.get("/games/list")
    assert resp.status_code == 200
    assert len(resp.json()["games"]) == 2


@pytest.mark.asyncio
async def test_get_games_list_filters_by_status(db_pool, clean, http_client):
    game = await _start_game(http_client)
    await http_client.post(f"/games/{game['game_id']}/finish")
    playing = await http_client.get("/games/list", params={"status": "playing"})
    finished = await http_client.get("/games/list", params={"status": "finished"})
    assert len(playing.json()["games"]) == 0
    assert len(finished.json()["games"]) == 1
