import pytest
import pytest_asyncio
import aiomysql
from datetime import datetime
from dotenv import load_dotenv
import os
import uuid

from app.domain.game import GameMode, GameStatus
from app.domain.room import RoomStatus
from app.infrastructure.db.game_repository import MysqlGameRepository
from app.infrastructure.db.room_repository import MysqlRoomRepository
from app.infrastructure.db.player_repository import MysqlPlayerRepository
from app.usecase.list_rooms_games_usecase import ListRoomsUseCase, ListGamesUseCase


load_dotenv()


@pytest_asyncio.fixture
async def db_pool():
    """
    Fixture pour créer un pool de connexions MySQL.
    Se connecte avant chaque test, se déconnecte après.
    """
    host = os.getenv("DB_HOST", "localhost")
    if host == "db":
        host = "localhost"
    
    pool = await aiomysql.create_pool(
        host=host,
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "flipper"),
        password=os.getenv("DB_PASSWORD"),
        db=os.getenv("MYSQL_DATABASE", "flipper"),
        minsize=1,
        maxsize=5,
        connect_timeout=10,
    )
    
    yield pool
    
    pool.close()
    await pool.wait_closed()


@pytest.mark.asyncio
async def test_list_rooms_by_status_waiting(db_pool):
    """Teste la liste des rooms avec status WAITING."""
    room_repo = MysqlRoomRepository(db_pool)
    
    # Créer 2 rooms en attente
    room1 = await room_repo.create(GameMode.SOLO)
    room2 = await room_repo.create(GameMode.SOLO)
    
    # Lister les rooms WAITING
    usecase = ListRoomsUseCase(room_repo)
    result = await usecase.execute(status="waiting")
    
    assert len(result["rooms"]) >= 2
    assert all(r.status == RoomStatus.WAITING for r in result["rooms"])
    assert room1.code in [r.code for r in result["rooms"]]
    assert room2.code in [r.code for r in result["rooms"]]


@pytest.mark.asyncio
async def test_list_rooms_no_status_filter(db_pool):
    """Teste la liste de toutes les rooms sans filtre."""
    room_repo = MysqlRoomRepository(db_pool)
    
    room = await room_repo.create(GameMode.SOLO)
    
    usecase = ListRoomsUseCase(room_repo)
    result = await usecase.execute(status=None)
    
    assert len(result["rooms"]) >= 1


@pytest.mark.asyncio
async def test_list_games_by_status_playing(db_pool):
    """Teste la liste des games avec status PLAYING."""
    game_repo = MysqlGameRepository(db_pool)
    player_repo = MysqlPlayerRepository(db_pool)
    room_repo = MysqlRoomRepository(db_pool)
    
    player = await player_repo.create(pseudo=f"test_player_list_{uuid.uuid4().hex[:8]}")
    
    room = await room_repo.create(GameMode.SOLO)
    
    game1 = await game_repo.create(player_id=player.id, room_id=room.id, mode=GameMode.SOLO)
    game2 = await game_repo.create(player_id=player.id, room_id=room.id, mode=GameMode.SOLO)
    
    # Lister les games créées PLAYING
    usecase = ListGamesUseCase(game_repo)
    result = await usecase.execute(status="playing")
    
    assert len(result["games"]) >= 2
    assert all(g.status == GameStatus.PLAYING for g in result["games"])
    assert game1.id in [g.id for g in result["games"]]
    assert game2.id in [g.id for g in result["games"]]


@pytest.mark.asyncio
async def test_list_games_finished(db_pool):
    """Teste la liste des games avec status FINISHED."""
    game_repo = MysqlGameRepository(db_pool)
    player_repo = MysqlPlayerRepository(db_pool)
    room_repo = MysqlRoomRepository(db_pool)
    
    # Créer un joueur avec pseudo unique
    player = await player_repo.create(pseudo=f"test_player_finished_{uuid.uuid4().hex[:8]}")
    
    room = await room_repo.create(GameMode.SOLO)
    
    # Créer une game et la terminer
    game = await game_repo.create(player_id=player.id, room_id=room.id, mode=GameMode.SOLO)
    finished_game = await game_repo.finish(game.id)
    
    # Lister les games FINISHED
    usecase = ListGamesUseCase(game_repo)
    result = await usecase.execute(status="finished")
    
    assert any(g.id == game.id for g in result["games"])
    assert any(g.status == GameStatus.FINISHED for g in result["games"])


@pytest.mark.asyncio
async def test_list_games_no_status_filter(db_pool):
    """Teste la liste de toutes les games sans filtre."""
    game_repo = MysqlGameRepository(db_pool)
    player_repo = MysqlPlayerRepository(db_pool)
    room_repo = MysqlRoomRepository(db_pool)
    
    player = await player_repo.create(pseudo=f"test_player_nofilter_{uuid.uuid4().hex[:8]}")
    room = await room_repo.create(GameMode.SOLO)
    game = await game_repo.create(player_id=player.id, room_id=room.id, mode=GameMode.SOLO)
    
    usecase = ListGamesUseCase(game_repo)
    result = await usecase.execute(status=None)
    
    assert len(result["games"]) >= 1


@pytest.mark.asyncio
async def test_list_games_empty_result(db_pool):
    """Teste quand aucune game n'existe pour le status."""
    game_repo = MysqlGameRepository(db_pool)
    
    usecase = ListGamesUseCase(game_repo)
    result = await usecase.execute(status="finished")
    
    # Vérifier que le résultat est une liste 
    assert isinstance(result["games"], list)
