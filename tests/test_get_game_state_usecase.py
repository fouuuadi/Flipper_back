import pytest
import pytest_asyncio

from app.domain.exceptions import GameNotFoundError
from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.infrastructure.db.game_event_repository import PgGameEventRepository
from app.infrastructure.db.game_repository import PgGameRepository
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository
from app.usecase.add_game_event_usecase import AddGameEventUseCase
from app.usecase.get_game_state_usecase import GetGameStateUseCase
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
    return GetGameStateUseCase(
        game_repo=repositories["game"],
        event_repo=repositories["event"],
    )


@pytest.mark.asyncio
async def test_get_game_state_with_events(usecase, repositories, clean_tables):
    start_usecase = StartGameUseCase(
        player_repo=repositories["player"],
        room_repo=repositories["room"],
        game_repo=repositories["game"],
        event_repo=repositories["event"],
    )
    start_result = await start_usecase.execute(pseudo="alice", mode=GameMode.SOLO)
    game_id = start_result["game"].id

    add_usecase = AddGameEventUseCase(
        game_repo=repositories["game"],
        event_repo=repositories["event"],
    )
    await add_usecase.execute(
        game_id=game_id,
        event_type=GameEventType.BUMPER_HIT,
        points=100,
    )
    await add_usecase.execute(
        game_id=game_id,
        event_type=GameEventType.BUMPER_HIT,
        points=50,
    )

    result = await usecase.execute(game_id=game_id)

    assert result["game"].id == game_id
    assert result["game"].score == 150
    assert len(result["events"]) >= 3
    assert result["events"][0].type == GameEventType.BUMPER_HIT


@pytest.mark.asyncio
async def test_get_game_state_nonexistent(usecase, clean_tables):
    with pytest.raises(GameNotFoundError, match="n'existe pas"):
        await usecase.execute(game_id=999)
