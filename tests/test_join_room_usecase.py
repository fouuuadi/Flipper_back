import pytest
import pytest_asyncio
import aiomysql
from dotenv import load_dotenv
import os
from app.domain.game import GameMode
from app.usecase.join_room_usecase import JoinRoomUseCase
from app.usecase.create_room_usecase import CreateRoomUseCase
from app.infrastructure.db.room_repository import MysqlRoomRepository
from app.infrastructure.db.game_repository import MysqlGameRepository
from app.infrastructure.db.player_repository import MysqlPlayerRepository


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
    }


@pytest_asyncio.fixture
async def usecase(repositories):

    return JoinRoomUseCase(
        room_repository=repositories["room"],
        game_repository=repositories["game"]
    )


@pytest_asyncio.fixture
async def create_room_usecase(repositories):

    return CreateRoomUseCase(repositories["room"])


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


@pytest.mark.asyncio
async def test_join_room_valid_code(usecase, create_room_usecase, clean_tables):

    create_result = await create_room_usecase.execute(mode=GameMode.SOLO)
    room_code = create_result["room"].code
    
    result = await usecase.execute(room_code)
    
    assert result["room"] is not None
    assert result["room"].code == room_code
    assert result["room"].mode == GameMode.SOLO
    
    assert isinstance(result["games"], list)


@pytest.mark.asyncio
async def test_join_room_invalid_code(usecase, clean_tables):

    with pytest.raises(ValueError) as exc_info:
        await usecase.execute("INVALID")
    
    assert "Room INVALID not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_join_room_with_games(usecase, create_room_usecase, repositories, clean_tables):

    create_result = await create_room_usecase.execute(mode=GameMode.SOLO)
    room = create_result["room"]
    room_code = room.code
    
    player_repo = repositories["player"]
    player = await player_repo.create(pseudo="test_player")
    
    # Créer une game dans la room
    game_repo = repositories["game"]
    game = await game_repo.create(
        player_id=player.id, 
        room_id=room.id,
        mode=GameMode.SOLO
    )
    
    result = await usecase.execute(room_code)
    
    assert isinstance(result["games"], list)
    assert len(result["games"]) == 1
    assert result["games"][0].id == game.id
