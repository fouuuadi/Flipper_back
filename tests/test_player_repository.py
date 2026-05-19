import pytest
import pytest_asyncio
import aiomysql
from dotenv import load_dotenv
import os
from app.domain.exceptions import PlayerAlreadyExistsError
from app.infrastructure.db.player_repository import PlayerRepository


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


@pytest_asyncio.fixture
async def repository(db_pool):
    """
    Fixture pour créer une instance du PlayerRepository.
    """
    return PlayerRepository(db_pool)


@pytest_asyncio.fixture
async def clean_table(db_pool):
    """
    Fixture pour nettoyer la table players avant chaque test.
    """
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            await cursor.execute("DELETE FROM players")
            await cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            await conn.commit()
    
    yield
    
    async with db_pool.acquire() as conn:
        try:
            await conn.rollback()  
            async with conn.cursor() as cursor:
                await cursor.execute("SET FOREIGN_KEY_CHECKS=0")
                await cursor.execute("DELETE FROM players")
                await cursor.execute("SET FOREIGN_KEY_CHECKS=1")
                await conn.commit()
        except Exception:
            pass  


@pytest.mark.asyncio
async def test_create_and_get_by_id(repository, clean_table):
    """
    Test : créer un joueur et le récupérer par ID.
    """
    # Créer un joueur
    player = await repository.create("alice")
    
    # Vérifier que le joueur a un ID
    assert player.id is not None
    assert player.pseudo == "alice"
    assert player.created_at is not None
    
    # Récupérer le joueur par ID
    retrieved = await repository.get_by_id(player.id)
    
    assert retrieved is not None
    assert retrieved.id == player.id
    assert retrieved.pseudo == "alice"


@pytest.mark.asyncio
async def test_create_and_get_by_pseudo(repository, clean_table):
    """
    Test : créer un joueur et le récupérer par pseudo.
    """
    # Créer un joueur
    created = await repository.create("bob")
    
    # Récupérer le joueur par pseudo
    retrieved = await repository.get_by_pseudo("bob")
    
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.pseudo == "bob"
    assert retrieved.created_at is not None


@pytest.mark.asyncio
async def test_duplicate_pseudo_raises_error(repository, clean_table):
    """
    Test : tenter de créer deux joueurs avec le même pseudo lève une erreur.
    """
    # Créer le premier joueur
    await repository.create("charlie")
    
    # Tenter de créer un deuxième avec le même pseudo
    with pytest.raises(PlayerAlreadyExistsError, match="déjà utilisé"):
        await repository.create("charlie")


@pytest.mark.asyncio
async def test_get_nonexistent_player(repository, clean_table):
    """
    Test : récupérer un joueur inexistant retourne None.
    """
    result = await repository.get_by_id(999)
    assert result is None
    
    result = await repository.get_by_pseudo("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_multiple_players(repository, clean_table):
    """
    Test : créer et récupérer plusieurs joueurs.
    """
    p1 = await repository.create("player1")
    p2 = await repository.create("player2")
    p3 = await repository.create("player3")
    
    assert p1.id != p2.id != p3.id
    
    assert (await repository.get_by_id(p1.id)).pseudo == "player1"
    assert (await repository.get_by_id(p2.id)).pseudo == "player2"
    assert (await repository.get_by_id(p3.id)).pseudo == "player3"