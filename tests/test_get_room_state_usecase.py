import pytest
import pytest_asyncio

from app.domain.exceptions import RoomNotFoundError
from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.infrastructure.db.game_event_repository import PgGameEventRepository
from app.infrastructure.db.game_repository import PgGameRepository
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository
from app.usecase.add_game_event_usecase import AddGameEventUseCase
from app.usecase.get_room_state_usecase import GetRoomStateUseCase
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
    return GetRoomStateUseCase(
        room_repo=repositories["room"],
        game_repo=repositories["game"],
        event_repo=repositories["event"],
    )


@pytest.mark.asyncio
async def test_get_room_state_with_games_and_events(
    usecase, repositories, db_pool, clean_tables
):
    from app.infrastructure.db.unit_of_work import PgUnitOfWork

    start_usecase = StartGameUseCase(lambda: PgUnitOfWork(db_pool))

    result1 = await start_usecase.execute(pseudo="alice", mode=GameMode.ONE_V_ONE)
    room_code = result1["room"].code
    game1_id = result1["game"].id

    result2 = await start_usecase.execute(
        pseudo="bob",
        mode=GameMode.ONE_V_ONE,
        room_code=room_code,
    )
    game2_id = result2["game"].id

    add_usecase = AddGameEventUseCase(
        game_repo=repositories["game"],
        event_repo=repositories["event"],
    )
    await add_usecase.execute(
        game_id=game1_id,
        event_type=GameEventType.BUMPER_HIT,
        points=100,
    )
    await add_usecase.execute(
        game_id=game2_id,
        event_type=GameEventType.BUMPER_HIT,
        points=50,
    )

    result = await usecase.execute(room_code=room_code)

    assert result["room"].code == room_code
    assert len(result["games_with_events"]) == 2
    for item in result["games_with_events"]:
        assert item["game"] is not None
        assert len(item["events"]) >= 1


@pytest.mark.asyncio
async def test_get_room_state_nonexistent(usecase, clean_tables):
    with pytest.raises(RoomNotFoundError, match="n'existe pas"):
        await usecase.execute(room_code="INVALID")
