import pytest
import pytest_asyncio
import aiomysql
from dotenv import load_dotenv
import os
from app.domain.exceptions import RoomNotFoundError
from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.usecase.start_game_usecase import StartGameUseCase
from app.usecase.add_game_event_usecase import AddGameEventUseCase
from app.usecase.get_room_state_usecase import GetRoomStateUseCase
from app.infrastructure.db.player_repository import PlayerRepository
from app.infrastructure.db.room_repository import RoomRepository
from app.infrastructure.db.game_repository import GameRepository
from app.infrastructure.db.game_event_repository import GameEventRepository


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
        "player": PlayerRepository(db_pool),
        "room": RoomRepository(db_pool),
        "game": GameRepository(db_pool),
        "event": GameEventRepository(db_pool),
    }


@pytest_asyncio.fixture
async def usecase(repositories):

    return GetRoomStateUseCase(
        room_repo=repositories["room"],
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
async def test_get_room_state_with_games_and_events(usecase, repositories, clean_tables):
    """
    Test : récupérer l'état d'une room retourne room + games + events.
    """
    start_usecase = StartGameUseCase(
        player_repo=repositories["player"],
        room_repo=repositories["room"],
        game_repo=repositories["game"],
        event_repo=repositories["event"]
    )
    
    result1 = await start_usecase.execute(
        pseudo="alice",
        mode=GameMode.ONE_V_ONE
    )
    room_code = result1["room"].code
    game1_id = result1["game"].id
    
    result2 = await start_usecase.execute(
        pseudo="bob",
        mode=GameMode.ONE_V_ONE,
        room_code=room_code
    )
    game2_id = result2["game"].id
    
    add_usecase = AddGameEventUseCase(
        game_repo=repositories["game"],
        event_repo=repositories["event"]
    )
    
    await add_usecase.execute(
        game_id=game1_id,
        event_type=GameEventType.BUMPER_HIT,
        points=100
    )
    
    await add_usecase.execute(
        game_id=game2_id,
        event_type=GameEventType.BUMPER_HIT,
        points=50
    )
    
    result = await usecase.execute(room_code=room_code)
    
    assert result["room"].code == room_code
    assert len(result["games_with_events"]) == 2
    
    for item in result["games_with_events"]:
        assert item["game"] is not None
        assert len(item["events"]) >= 1  


@pytest.mark.asyncio
async def test_get_room_state_nonexistent(usecase, clean_tables):

    with pytest.raises(RoomNotFoundError, match="n'existe pas"):
        await usecase.execute(room_code="INVALID")
