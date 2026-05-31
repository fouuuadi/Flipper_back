import pytest
import pytest_asyncio

from app.domain.exceptions import GameNotFoundError, GameNotPlayableError
from app.domain.game import GameMode, GameStatus
from app.domain.game_event import GameEventType
from app.infrastructure.db.game_event_repository import PgGameEventRepository
from app.infrastructure.db.game_repository import PgGameRepository
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository
from app.infrastructure.db.unit_of_work import PgUnitOfWork
from app.usecase.add_game_event_usecase import AddGameEventUseCase
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
    return AddGameEventUseCase(
        game_repo=repositories["game"],
        event_repo=repositories["event"],
    )


async def _start_game(db_pool, pseudo: str):
    start_usecase = StartGameUseCase(lambda: PgUnitOfWork(db_pool))
    return await start_usecase.execute(pseudo=pseudo, mode=GameMode.SOLO)


@pytest.mark.asyncio
async def test_add_event_increases_score(usecase, db_pool, clean_tables):
    start_result = await _start_game(db_pool, "alice")
    game_id = start_result["game"].id
    initial_score = start_result["game"].score

    result = await usecase.execute(
        game_id=game_id,
        event_type=GameEventType.BUMPER_HIT,
        points=100,
    )

    assert result["game"].score == initial_score + 100
    assert result["event"].type == GameEventType.BUMPER_HIT
    assert result["event"].points == 100


@pytest.mark.asyncio
async def test_add_event_without_points(usecase, db_pool, clean_tables):
    start_result = await _start_game(db_pool, "bob")
    game_id = start_result["game"].id
    initial_score = start_result["game"].score

    result = await usecase.execute(
        game_id=game_id,
        event_type=GameEventType.BALL_LOST,
        points=0,
    )

    assert result["game"].score == initial_score
    assert result["event"].type == GameEventType.BALL_LOST


@pytest.mark.asyncio
async def test_add_event_nonexistent_game(usecase, clean_tables):
    with pytest.raises(GameNotFoundError, match="n'existe pas"):
        await usecase.execute(
            game_id=999,
            event_type=GameEventType.BUMPER_HIT,
            points=50,
        )


@pytest.mark.asyncio
async def test_add_event_finished_game(usecase, db_pool, clean_tables):
    start_result = await _start_game(db_pool, "charlie")
    game_id = start_result["game"].id

    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE games SET status = $1 WHERE id = $2",
            GameStatus.FINISHED.value,
            game_id,
        )

    with pytest.raises(GameNotPlayableError, match="en état"):
        await usecase.execute(
            game_id=game_id,
            event_type=GameEventType.GAME_OVER,
            points=0,
        )


@pytest.mark.asyncio
async def test_multiple_events_accumulate_score(usecase, db_pool, clean_tables):
    start_result = await _start_game(db_pool, "dave")
    game_id = start_result["game"].id
    score = 0

    events = [
        (GameEventType.BUMPER_HIT, 100),
        (GameEventType.BUMPER_HIT, 50),
        (GameEventType.FLIPPER_HIT, 200),
    ]

    for event_type, points in events:
        result = await usecase.execute(
            game_id=game_id,
            event_type=event_type,
            points=points,
        )
        score += points
        assert result["game"].score == score
