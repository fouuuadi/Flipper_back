import pytest
import pytest_asyncio

from app.domain.exceptions import RoomNotFoundError
from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.infrastructure.db.game_event_repository import PgGameEventRepository
from app.infrastructure.db.game_repository import PgGameRepository
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository
from app.usecase.start_game_usecase import StartGameUseCase


@pytest_asyncio.fixture
async def repositories(db_pool):
    return {
        "player": PgPlayerRepository(db_pool),
        "room": PgRoomRepository(db_pool),
        "game": PgGameRepository(db_pool),
        "event": PgGameEventRepository(db_pool),
    }


@pytest_asyncio.fixture
async def usecase(repositories):
    return StartGameUseCase(
        player_repo=repositories["player"],
        room_repo=repositories["room"],
        game_repo=repositories["game"],
        event_repo=repositories["event"],
    )


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
async def test_start_solo_existing_player(usecase, repositories, clean_tables):
    existing_player = await repositories["player"].create("fouad")

    result = await usecase.execute(pseudo="fouad", mode=GameMode.SOLO)

    assert result["player"].id == existing_player.id
    assert result["player"].pseudo == "fouad"
    assert result["room"].id is not None
    assert result["game"].id is not None
    assert result["game"].player_id == existing_player.id


@pytest.mark.asyncio
async def test_start_1v1_with_existing_room(usecase, repositories, clean_tables):
    existing_room = await repositories["room"].create(GameMode.ONE_V_ONE)

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
async def test_start_with_nonexistent_room_code(usecase, clean_tables):
    with pytest.raises(RoomNotFoundError, match="n'existe pas"):
        await usecase.execute(
            pseudo="dave",
            mode=GameMode.SOLO,
            room_code="INVALID",
        )


@pytest.mark.asyncio
async def test_start_creates_game_started_event(usecase, clean_tables):
    result = await usecase.execute(pseudo="gabrielle", mode=GameMode.SOLO)

    assert result["event"].game_id == result["game"].id
    assert result["event"].type == GameEventType.GAME_STARTED
    assert result["event"].points == 0
