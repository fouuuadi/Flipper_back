import pytest
import pytest_asyncio
import aiomysql
from dotenv import load_dotenv
import os
import uuid

from app.domain.exceptions import PlayerNotFoundError
from app.infrastructure.db.player_repository import MysqlPlayerRepository
from app.usecase.create_or_get_player_usecase import CreateOrGetPlayerUseCase
from app.usecase.get_player_usecase import GetPlayerUseCase


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
        db=os.getenv("MYSQL_DATABASE", "flipper"),
        minsize=1,
        maxsize=5,
        connect_timeout=10,
    )
    
    yield pool
    
    pool.close()
    await pool.wait_closed()


@pytest.mark.asyncio
async def test_create_player(db_pool):
    """Teste la création d'un joueur avec pseudo valide."""
    player_repo = MysqlPlayerRepository(db_pool)
    
    pseudo = f"test_player_{uuid.uuid4().hex[:8]}"
    
    usecase = CreateOrGetPlayerUseCase(player_repo)
    result = await usecase.execute(pseudo=pseudo)
    
    assert result["created"] is True
    assert result["player"].pseudo == pseudo
    assert result["player"].id is not None
    assert result["player"].created_at is not None


@pytest.mark.asyncio
async def test_get_existing_player(db_pool):
    """Teste la récupération d'un joueur existant par pseudo."""
    player_repo = MysqlPlayerRepository(db_pool)
    
    pseudo = f"test_existing_{uuid.uuid4().hex[:8]}"
    usecase = CreateOrGetPlayerUseCase(player_repo)
    result1 = await usecase.execute(pseudo=pseudo)
    
    assert result1["created"] is True
    player_id = result1["player"].id
    
    result2 = await usecase.execute(pseudo=pseudo)
    
    assert result2["created"] is False
    assert result2["player"].id == player_id
    assert result2["player"].pseudo == pseudo


@pytest.mark.asyncio
async def test_get_player_by_id(db_pool):
    """Teste la récupération d'un joueur par ID."""
    player_repo = MysqlPlayerRepository(db_pool)
    
    pseudo = f"test_getid_{uuid.uuid4().hex[:8]}"
    player = await player_repo.create(pseudo)
    
    usecase = GetPlayerUseCase(player_repo)
    result = await usecase.execute(player_id=player.id)
    
    assert result["player"].id == player.id
    assert result["player"].pseudo == pseudo


@pytest.mark.asyncio
async def test_get_player_not_found(db_pool):
    """Teste la récupération d'un joueur inexistant."""
    player_repo = MysqlPlayerRepository(db_pool)
    
    usecase = GetPlayerUseCase(player_repo)
    
    with pytest.raises(PlayerNotFoundError):
        await usecase.execute(player_id=99999)


@pytest.mark.asyncio
async def test_invalid_pseudo_empty(db_pool):
    """Teste qu'un pseudo vide lève une erreur."""
    player_repo = MysqlPlayerRepository(db_pool)
    
    usecase = CreateOrGetPlayerUseCase(player_repo)
    
    with pytest.raises(ValueError):
        await usecase.execute(pseudo="")


@pytest.mark.asyncio
async def test_invalid_player_id(db_pool):
    """Teste qu'un ID invalide lève une erreur."""
    player_repo = MysqlPlayerRepository(db_pool)
    
    usecase = GetPlayerUseCase(player_repo)
    
    with pytest.raises(ValueError):
        await usecase.execute(player_id=-1)
