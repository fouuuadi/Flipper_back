import pytest
import pytest_asyncio
import aiomysql
from dotenv import load_dotenv
import os
from app.domain.game import GameMode
from app.usecase.start_game_usecase import StartGameUseCase
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
    Fixture pour créer une instance du StartGameUseCase.
    """
    return StartGameUseCase(
        player_repo=repositories["player"],
        room_repo=repositories["room"],
        game_repo=repositories["game"],
        event_repo=repositories["event"]
    )


@pytest_asyncio.fixture
async def clean_tables(db_pool):
    """
    Fixture pour nettoyer les tables avant chaque test.
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
    
    g


@pytest.mark.asyncio
async def test_start_solo_new_player(usecase, clean_tables):
    """
    Test : démarrer une partie en SOLO avec un nouveau joueur.
    """
    result = await usecase.execute(
        pseudo="oscar",
        mode=GameMode.SOLO
    )
    
    # Vérifier que tous les objets ont été créés
    assert result["player"] is not None
    assert result["player"].id is not None
    assert result["player"].pseudo == "oscar"
    
    assert result["room"] is not None
    assert result["room"].id is not None
    assert result["room"].code is not None
    assert result["room"].mode == GameMode.SOLO
    
    assert result["game"] is not None
    assert result["game"].id is not None
    assert result["game"].player_id == result["player"].id
    assert result["game"].mode == GameMode.SOLO
    assert result["game"].score == 0
    
    assert result["event"] is not None
    assert result["event"].id is not None
    assert result["event"].game_id == result["game"].id


@pytest.mark.asyncio
async def test_start_solo_existing_player(usecase, repositories, clean_tables):
    """
    Test : démarrer une partie avec un joueur existant.
    Doit réutiliser le joueur, créer nouvelle room + game.
    """
    # Créer un joueur existant
    existing_player = await repositories["player"].create("fouad")
    
    # Démarrer une partie avec le même pseudo
    result = await usecase.execute(
        pseudo="fouad",
        mode=GameMode.SOLO
    )
    
    # Vérifier que le joueur est réutilisé (même ID)
    assert result["player"].id == existing_player.id
    assert result["player"].pseudo == "fouad"
    
    # Vérifier que new room et game sont créées
    assert result["room"].id is not None
    assert result["game"].id is not None
    assert result["game"].player_id == existing_player.id


@pytest.mark.asyncio
async def test_start_1v1_with_existing_room(usecase, repositories, clean_tables):
    """
    Test : rejoindre une room existante via son code.
    Doit créer player + game avec room existante.
    """
    # Créer une room existante
    existing_room = await repositories["room"].create(GameMode.ONE_V_ONE)
    
    # Démarrer une partie en se joignant à cette room
    result = await usecase.execute(
        pseudo="oscar",
        mode=GameMode.ONE_V_ONE,
        room_code=existing_room.code
    )
    
    # Vérifier que la room existante est réutilisée
    assert result["room"].id == existing_room.id
    assert result["room"].code == existing_room.code
    
    # Vérifier que player et game sont créés
    assert result["player"].id is not None
    assert result["game"].id is not None
    assert result["game"].player_id == result["player"].id


@pytest.mark.asyncio
async def test_start_with_nonexistent_room_code(usecase, clean_tables):
    """
    Test : essayer de rejoindre une room inexistante lève une erreur.
    """
    with pytest.raises(ValueError, match="n'existe pas"):
        await usecase.execute(
            pseudo="dave",
            mode=GameMode.SOLO,
            room_code="INVALID"
        )


@pytest.mark.asyncio
async def test_start_creates_game_started_event(usecase, repositories, clean_tables):
    """
    Test : vérifier que l'événement GAME_STARTED est créé.
    """
    result = await usecase.execute(
        pseudo="gabrielle",
        mode=GameMode.SOLO
    )
    
    # Vérifier l'événement
    from app.domain.game_event import GameEventType
    assert result["event"].game_id == result["game"].id
    assert result["event"].type == GameEventType.GAME_STARTED
    assert result["event"].points == 0
