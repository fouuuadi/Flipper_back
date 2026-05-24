import uuid

import pytest

from app.domain.game import GameMode, GameStatus
from app.domain.room import RoomStatus
from app.infrastructure.db.game_repository import PgGameRepository
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository
from app.usecase.list_rooms_games_usecase import ListGamesUseCase, ListRoomsUseCase


@pytest.mark.asyncio
async def test_list_rooms_by_status_waiting(db_pool, clean_tables):
    room_repo = PgRoomRepository(db_pool)

    room1 = await room_repo.create(GameMode.SOLO)
    room2 = await room_repo.create(GameMode.SOLO)

    usecase = ListRoomsUseCase(room_repo)
    result = await usecase.execute(status="waiting")

    assert len(result["rooms"]) >= 2
    assert all(r.status == RoomStatus.WAITING for r in result["rooms"])
    assert room1.code in [r.code for r in result["rooms"]]
    assert room2.code in [r.code for r in result["rooms"]]


@pytest.mark.asyncio
async def test_list_rooms_no_status_filter(db_pool, clean_tables):
    room_repo = PgRoomRepository(db_pool)
    await room_repo.create(GameMode.SOLO)

    usecase = ListRoomsUseCase(room_repo)
    result = await usecase.execute(status=None)

    assert len(result["rooms"]) >= 1


@pytest.mark.asyncio
async def test_list_games_by_status_playing(db_pool, clean_tables):
    game_repo = PgGameRepository(db_pool)
    player_repo = PgPlayerRepository(db_pool)
    room_repo = PgRoomRepository(db_pool)

    player = await player_repo.create(pseudo=f"tpl_{uuid.uuid4().hex[:8]}")
    room = await room_repo.create(GameMode.SOLO)
    game1 = await game_repo.create(player_id=player.id, room_id=room.id, mode=GameMode.SOLO)
    game2 = await game_repo.create(player_id=player.id, room_id=room.id, mode=GameMode.SOLO)

    usecase = ListGamesUseCase(game_repo)
    result = await usecase.execute(status="playing")

    assert len(result["games"]) >= 2
    assert all(g.status == GameStatus.PLAYING for g in result["games"])
    assert game1.id in [g.id for g in result["games"]]
    assert game2.id in [g.id for g in result["games"]]


@pytest.mark.asyncio
async def test_list_games_finished(db_pool, clean_tables):
    game_repo = PgGameRepository(db_pool)
    player_repo = PgPlayerRepository(db_pool)
    room_repo = PgRoomRepository(db_pool)

    player = await player_repo.create(pseudo=f"tpf_{uuid.uuid4().hex[:8]}")
    room = await room_repo.create(GameMode.SOLO)
    game = await game_repo.create(player_id=player.id, room_id=room.id, mode=GameMode.SOLO)
    await game_repo.finish(game.id)

    usecase = ListGamesUseCase(game_repo)
    result = await usecase.execute(status="finished")

    assert any(g.id == game.id for g in result["games"])
    assert any(g.status == GameStatus.FINISHED for g in result["games"])


@pytest.mark.asyncio
async def test_list_games_no_status_filter(db_pool, clean_tables):
    game_repo = PgGameRepository(db_pool)
    player_repo = PgPlayerRepository(db_pool)
    room_repo = PgRoomRepository(db_pool)

    player = await player_repo.create(pseudo=f"tpn_{uuid.uuid4().hex[:8]}")
    room = await room_repo.create(GameMode.SOLO)
    await game_repo.create(player_id=player.id, room_id=room.id, mode=GameMode.SOLO)

    usecase = ListGamesUseCase(game_repo)
    result = await usecase.execute(status=None)

    assert len(result["games"]) >= 1


@pytest.mark.asyncio
async def test_list_games_empty_result(db_pool, clean_tables):
    game_repo = PgGameRepository(db_pool)

    usecase = ListGamesUseCase(game_repo)
    result = await usecase.execute(status="finished")

    assert isinstance(result["games"], list)
