import pytest
import pytest_asyncio

from app.domain.exceptions import GameAlreadyFinishedError, GameNotFoundError
from app.domain.game import GameMode, GameStatus
from app.domain.game_event import GameEventType
from app.infrastructure.db.game_event_repository import PgGameEventRepository
from app.infrastructure.db.game_repository import PgGameRepository
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository
from app.usecase.finish_game_usecase import FinishGameUseCase
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
    return FinishGameUseCase(
        game_repo=repositories["game"],
        event_repo=repositories["event"],
    )


async def _start_game(repositories, pseudo: str):
    start_usecase = StartGameUseCase(
        player_repo=repositories["player"],
        room_repo=repositories["room"],
        game_repo=repositories["game"],
        event_repo=repositories["event"],
    )
    return await start_usecase.execute(pseudo=pseudo, mode=GameMode.SOLO)


@pytest.mark.asyncio
async def test_finish_game_playing(usecase, repositories, clean_tables):
    start_result = await _start_game(repositories, "alice")
    game_id = start_result["game"].id

    result = await usecase.execute(game_id=game_id)

    assert result["game"].status == GameStatus.FINISHED
    assert result["game"].finished_at is not None
    assert result["event"].type == GameEventType.GAME_OVER
    assert result["event"].game_id == game_id


@pytest.mark.asyncio
async def test_finish_game_nonexistent(usecase, clean_tables):
    with pytest.raises(GameNotFoundError, match="n'existe pas"):
        await usecase.execute(game_id=999)


@pytest.mark.asyncio
async def test_finish_game_already_finished(usecase, repositories, clean_tables):
    start_result = await _start_game(repositories, "bob")
    game_id = start_result["game"].id

    await usecase.execute(game_id=game_id)

    with pytest.raises(GameAlreadyFinishedError, match="en état"):
        await usecase.execute(game_id=game_id)
