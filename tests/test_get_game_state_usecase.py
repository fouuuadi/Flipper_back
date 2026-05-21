import pytest
import pytest_asyncio
import aiomysql
from dotenv import load_dotenv
import os
from app.domain.exceptions import GameNotFoundError
from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.usecase.start_game_usecase import StartGameUseCase
from app.usecase.add_game_event_usecase import AddGameEventUseCase
from app.usecase.get_game_state_usecase import GetGameStateUseCase
from app.infrastructure.db.player_repository import MysqlPlayerRepository
from app.infrastructure.db.room_repository import MysqlRoomRepository
from app.infrastructure.db.game_repository import MysqlGameRepository
from app.infrastructure.db.game_event_repository import MysqlGameEventRepository


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
    
    yield pool
    
    pool.close()
    await pool.wait_closed()


@pytest_asyncio.fixture
async def repositories(db_pool):

    return {
        "player": MysqlPlayerRepository(db_pool),
        "room": MysqlRoomRepository(db_pool),
        "game": MysqlGameRepository(db_pool),
        "event": MysqlGameEventRepository(db_pool),
    }


@pytest_asyncio.fixture
async def usecase(repositories):
    """
    Fixture pour créer une instance du GetGameStateUseCase.
    """
    return GetGameStateUseCase(
        game_repo=repositories["game"],
        event_repo=repositories["event"]
    )


@pytest_asyncio.fixture
async def clean_tables(db_pool):

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            await cursor.execute("DELETE FROM game_events")
            await cursor.execute("DELETE FROM games")
            await cursor.execute("DELETE FROM rooms")
            await cursor.execute("DELETE FROM players")
            await cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            await conn.commit()
    
    yield
    
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            await cursor.execute("DELETE FROM game_events")
            await cursor.execute("DELETE FROM games")
            await cursor.execute("DELETE FROM rooms")
            await cursor.execute("DELETE FROM players")
            await cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            await conn.commit()


@pytest.mark.asyncio
async def test_get_game_state_with_events(usecase, repositories, clean_tables):
    """
    Test : récupérer l'état d'une game retourne game + events.
    """
    start_usecase = StartGameUseCase(
        player_repo=repositories["player"],
        room_repo=repositories["room"],
        game_repo=repositories["game"],
        event_repo=repositories["event"]
    )
    
    start_result = await start_usecase.execute(
        pseudo="alice",
        mode=GameMode.SOLO
    )
    game_id = start_result["game"].id
    
    add_usecase = AddGameEventUseCase(
        game_repo=repositories["game"],
        event_repo=repositories["event"]
    )
    
    await add_usecase.execute(
        game_id=game_id,
        event_type=GameEventType.BUMPER_HIT,
        points=100
    )
    
    await add_usecase.execute(
        game_id=game_id,
        event_type=GameEventType.BUMPER_HIT,
        points=50
    )
    
    result = await usecase.execute(game_id=game_id)
    
    assert result["game"].id == game_id
    assert result["game"].score == 150
    assert len(result["events"]) >= 3 
    
    assert result["events"][0].type == GameEventType.BUMPER_HIT  # Le dernier ajouté


@pytest.mark.asyncio
async def test_get_game_state_nonexistent(usecase, clean_tables):

    with pytest.raises(GameNotFoundError, match="n'existe pas"):
        await usecase.execute(game_id=999)
