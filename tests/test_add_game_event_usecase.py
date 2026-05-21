import pytest
import pytest_asyncio
import aiomysql
from dotenv import load_dotenv
import os
from app.domain.exceptions import GameNotFoundError, GameNotPlayableError
from app.domain.game import GameMode, GameStatus
from app.domain.game_event import GameEventType
from app.usecase.start_game_usecase import StartGameUseCase
from app.usecase.add_game_event_usecase import AddGameEventUseCase
from app.infrastructure.db.player_repository import MysqlPlayerRepository
from app.infrastructure.db.room_repository import MysqlRoomRepository
from app.infrastructure.db.game_repository import MysqlGameRepository
from app.infrastructure.db.game_event_repository import MysqlGameEventRepository


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
        "player": MysqlPlayerRepository(db_pool),
        "room": MysqlRoomRepository(db_pool),
        "game": MysqlGameRepository(db_pool),
        "event": MysqlGameEventRepository(db_pool),
    }


@pytest_asyncio.fixture
async def usecase(repositories):
    """
    Fixture pour créer une instance du AddGameEventUseCase.
    """
    return AddGameEventUseCase(
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
async def test_add_event_increases_score(usecase, repositories, clean_tables):
    """
    Test : ajouter un événement avec points augmente le score.
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
    initial_score = start_result["game"].score
    
    # 2. Ajouter un événement avec 100 points
    result = await usecase.execute(
        game_id=game_id,
        event_type=GameEventType.BUMPER_HIT,
        points=100
    )
    
    # 3. Vérifier que le score a augmenté
    assert result["game"].score == initial_score + 100
    assert result["event"].type == GameEventType.BUMPER_HIT
    assert result["event"].points == 100


@pytest.mark.asyncio
async def test_add_event_without_points(usecase, repositories, clean_tables):
    """
    Test : ajouter un événement sans points ne modifie pas le score.
    """
    # 1. Créer une game
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
    initial_score = start_result["game"].score
    
    # 2. Ajouter un événement sans points
    result = await usecase.execute(
        game_id=game_id,
        event_type=GameEventType.BALL_LOST,
        points=0
    )
    
    # 3. Vérifier que le score n'a pas changé
    assert result["game"].score == initial_score
    assert result["event"].type == GameEventType.BALL_LOST


@pytest.mark.asyncio
async def test_add_event_nonexistent_game(usecase, clean_tables):
    """
    Test : ajouter un événement à une game inexistante lève une erreur.
    """
    with pytest.raises(GameNotFoundError, match="n'existe pas"):
        await usecase.execute(
            game_id=999,
            event_type=GameEventType.BUMPER_HIT,
            points=50
        )


@pytest.mark.asyncio
async def test_add_event_finished_game(usecase, repositories, clean_tables):
    """
    Test : ajouter un événement à une game FINISHED lève une erreur.
    """
    # 1. Créer une game
    start_usecase = StartGameUseCase(
        player_repo=repositories["player"],
        room_repo=repositories["room"],
        game_repo=repositories["game"],
        event_repo=repositories["event"]
    )
    
    start_result = await start_usecase.execute(
        pseudo="charlie",
        mode=GameMode.SOLO
    )
    game_id = start_result["game"].id
    
    # 2. Marquer la game comme FINISHED
    async with repositories["game"].pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE games SET status = %s WHERE id = %s",
                (GameStatus.FINISHED.value, game_id)
            )
            await conn.commit()
    
    # 3. Essayer d'ajouter un événement
    with pytest.raises(GameNotPlayableError, match="en état"):
        await usecase.execute(
            game_id=game_id,
            event_type=GameEventType.GAME_OVER,
            points=0
        )


@pytest.mark.asyncio
async def test_multiple_events_accumulate_score(usecase, repositories, clean_tables):
    """
    Test : plusieurs événements accumulent correctement les points.
    """
    # 1. Créer une game
    start_usecase = StartGameUseCase(
        player_repo=repositories["player"],
        room_repo=repositories["room"],
        game_repo=repositories["game"],
        event_repo=repositories["event"]
    )
    
    start_result = await start_usecase.execute(
        pseudo="dave",
        mode=GameMode.SOLO
    )
    game_id = start_result["game"].id
    score = 0
    
    # 2. Ajouter plusieurs événements
    events = [
        (GameEventType.BUMPER_HIT, 100),
        (GameEventType.BUMPER_HIT, 50),
        (GameEventType.FLIPPER_HIT, 200),
    ]
    
    for event_type, points in events:
        result = await usecase.execute(
            game_id=game_id,
            event_type=event_type,
            points=points
        )
        score += points
        assert result["game"].score == score
