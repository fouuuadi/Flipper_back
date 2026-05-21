import pytest
import pytest_asyncio
import aiomysql
from dotenv import load_dotenv
import os
from app.domain.game import GameMode
from app.usecase.create_room_usecase import CreateRoomUseCase
from app.infrastructure.db.room_repository import MysqlRoomRepository


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
async def room_repo(db_pool):

    return MysqlRoomRepository(db_pool)


@pytest_asyncio.fixture
async def usecase(room_repo):

    return CreateRoomUseCase(room_repo)


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
async def test_create_room_solo(usecase, clean_tables):

    result = await usecase.execute(mode=GameMode.SOLO)
    
    assert result["room"] is not None
    assert result["room"].id is not None
    
    assert result["room"].code is not None
    assert len(result["room"].code) == 6
    assert all(c in '0123456789ABCDEF' for c in result["room"].code)
    
    assert result["room"].mode == GameMode.SOLO
    
    assert str(result["room"].status) == "RoomStatus.WAITING"


@pytest.mark.asyncio
async def test_create_room_1v1(usecase, clean_tables):

    result = await usecase.execute(mode=GameMode.ONE_V_ONE)
    
    assert result["room"] is not None
    assert result["room"].id is not None
    
    assert result["room"].mode == GameMode.ONE_V_ONE
    
    assert len(result["room"].code) == 6


@pytest.mark.asyncio
async def test_create_room_unique_codes(usecase, clean_tables):
    result1 = await usecase.execute(mode=GameMode.SOLO)
    result2 = await usecase.execute(mode=GameMode.SOLO)
    
    assert result1["room"].code != result2["room"].code
    
    # Vérifier que les deux rooms ont un ID
    assert result1["room"].id is not None
    assert result2["room"].id is not None
