import pytest
import pytest_asyncio

from app.domain.exceptions import RoomNotFoundError
from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository
from app.infrastructure.db.unit_of_work import PgUnitOfWork
from app.usecase.start_game_usecase import StartGameUseCase


@pytest_asyncio.fixture
async def uow_factory(db_pool):
    def _factory():
        return PgUnitOfWork(db_pool)
    return _factory


@pytest_asyncio.fixture
async def usecase(uow_factory):
    return StartGameUseCase(uow_factory)


@pytest.mark.asyncio
async def test_start_solo_new_player(usecase, clean_tables):
    result = await usecase.execute(pseudo="oscar", mode=GameMode.SOLO)

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
async def test_start_solo_existing_player(usecase, db_pool, clean_tables):
    existing_player = await PgPlayerRepository(db_pool).create("fouad")

    result = await usecase.execute(pseudo="fouad", mode=GameMode.SOLO)

    assert result["player"].id == existing_player.id
    assert result["player"].pseudo == "fouad"
    assert result["room"].id is not None
    assert result["game"].id is not None
    assert result["game"].player_id == existing_player.id


@pytest.mark.asyncio
async def test_start_1v1_with_existing_room(usecase, db_pool, clean_tables):
    existing_room = await PgRoomRepository(db_pool).create(GameMode.ONE_V_ONE)

    result = await usecase.execute(
        pseudo="oscar",
        mode=GameMode.ONE_V_ONE,
        room_code=existing_room.code,
    )

    assert result["room"].id == existing_room.id
    assert result["room"].code == existing_room.code
    assert result["player"].id is not None
    assert result["game"].id is not None
    assert result["game"].player_id == result["player"].id


@pytest.mark.asyncio
async def test_start_with_nonexistent_room_code_rolls_back(
    usecase, db_pool, clean_tables
):
    """Bug #68 : quand la recherche de room échoue, l'upsert du player effectué
    plus tôt dans le même `execute()` doit être rollback — pas de player orphelin."""
    with pytest.raises(RoomNotFoundError, match="n'existe pas"):
        await usecase.execute(
            pseudo="dave",
            mode=GameMode.SOLO,
            room_code="INVALID",
        )

    async with db_pool.acquire() as conn:
        n = await conn.fetchval(
            "SELECT COUNT(*) FROM players WHERE pseudo = $1", "dave"
        )
    assert n == 0


@pytest.mark.asyncio
async def test_start_creates_game_started_event(usecase, clean_tables):
    result = await usecase.execute(pseudo="gabrielle", mode=GameMode.SOLO)

    assert result["event"].game_id == result["game"].id
    assert result["event"].type == GameEventType.GAME_STARTED
    assert result["event"].points == 0
