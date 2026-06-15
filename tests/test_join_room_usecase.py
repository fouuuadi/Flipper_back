import pytest
import pytest_asyncio

from app.domain.exceptions import RoomNotFoundError
from app.domain.game import GameMode
from app.infrastructure.db.game_repository import PgGameRepository
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository
from app.usecase.create_room_usecase import CreateRoomUseCase
from app.usecase.join_room_usecase import JoinRoomUseCase


@pytest_asyncio.fixture
async def repositories(db_pool):
    return {
        "player": PgPlayerRepository(db_pool),
        "room": PgRoomRepository(db_pool),
        "game": PgGameRepository(db_pool),
    }


@pytest_asyncio.fixture
async def usecase(repositories):
    return JoinRoomUseCase(
        room_repository=repositories["room"],
        game_repository=repositories["game"],
    )


@pytest_asyncio.fixture
async def create_room_usecase(repositories):
    return CreateRoomUseCase(repositories["room"])


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
    with pytest.raises(RoomNotFoundError) as exc_info:
        await usecase.execute("INVALID")
    assert "Room INVALID not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_join_room_with_games(usecase, create_room_usecase, repositories, clean_tables):
    create_result = await create_room_usecase.execute(mode=GameMode.SOLO)
    room = create_result["room"]
    room_code = room.code

    player = await repositories["player"].create(pseudo="test_player")
    game = await repositories["game"].create(
        player_id=player.id,
        room_id=room.id,
        mode=GameMode.SOLO,
    )

    result = await usecase.execute(room_code)

    assert isinstance(result["games"], list)
    assert len(result["games"]) == 1
    assert result["games"][0].id == game.id
