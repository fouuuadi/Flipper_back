import pytest
import pytest_asyncio
import aiomysql
from dotenv import load_dotenv
import os
from app.domain.game import GameMode, GameStatus
from app.domain.game_event import GameEventType
from app.usecase.start_game_usecase import StartGameUseCase
from app.usecase.finish_game_usecase import FinishGameUseCase
from app.infrastructure.db.player_repository import PlayerRepository
from app.infrastructure.db.room_repository import RoomRepository
from app.infrastructure.db.game_repository import GameRepository
from app.infrastructure.db.game_event_repository import GameEventRepository


load_dotenv()


@pytest_asyncio.fixture
async def db_pool():
    """
    Fixture pour créer un pool de connexions MySQL.
    """
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
    """
    Fixture pour créer les instances des repositories.
    """
    return {
        "player": PlayerRepository(db_pool),
        "room": RoomRepository(db_pool),
        "game": GameRepository(db_pool),
        "event": GameEventRepository(db_pool),
    }


@pytest_asyncio.fixture
async def usecase(repositories):
    """
    Fixture pour créer une instance du FinishGameUseCase.
    """
    return FinishGameUseCase(
        game_repo=repositories["game"],
        event_repo=repositories["event"]
    )


@pytest_asyncio.fixture
async def clean_tables(db_pool):
    """
    Fixture pour nettoyer les tables avant et après chaque test.
    """
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
async def test_finish_game_playing(usecase, repositories, clean_tables):
    """
    Test : finir une game PLAYING met le status à FINISHED et crée event.
    """
    # 1. Créer une game via StartGameUseCase
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
    
    # 2. Finir la game
    result = await usecase.execute(game_id=game_id)
    
    # 3. Vérifier le status et finished_at
    assert result["game"].status == GameStatus.FINISHED
    assert result["game"].finished_at is not None
    
    # 4. Vérifier que l'événement GAME_OVER a été créé
    assert result["event"].type == GameEventType.GAME_OVER
    assert result["event"].game_id == game_id


@pytest.mark.asyncio
async def test_finish_game_nonexistent(usecase, clean_tables):
    """
    Test : finir une game inexistante lève une ValueError.
    """
    with pytest.raises(ValueError, match="n'existe pas"):
        await usecase.execute(game_id=999)


@pytest.mark.asyncio
async def test_finish_game_already_finished(usecase, repositories, clean_tables):
    """
    Test : finir une game déjà FINISHED lève une ValueError.
    """
    # 1. Créer et finir une game
    start_usecase = StartGameUseCase(
        player_repo=repositories["player"],
        room_repo=repositories["room"],
        game_repo=repositories["game"],
        event_repo=repositories["event"]
    )
    
    start_result = await start_usecase.execute(
        pseudo="bob",
        mode=GameMode.SOLO
    )
    game_id = start_result["game"].id
    
    # 2. Finir la game
    await usecase.execute(game_id=game_id)
    
    # 3. Essayer de finir deux fois
    with pytest.raises(ValueError, match="en état"):
        await usecase.execute(game_id=game_id)
