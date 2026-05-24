import pytest
import pytest_asyncio

from app.domain.game import GameMode
from app.infrastructure.db.room_repository import PgRoomRepository
from app.usecase.create_room_usecase import CreateRoomUseCase


@pytest_asyncio.fixture
async def room_repo(db_pool):
    return PgRoomRepository(db_pool)


@pytest_asyncio.fixture
async def usecase(room_repo):
    return CreateRoomUseCase(room_repo)


@pytest.mark.asyncio
async def test_create_room_solo(usecase, clean_tables):
    result = await usecase.execute(mode=GameMode.SOLO)

    assert result["room"] is not None
    assert result["room"].id is not None

    assert result["room"].code is not None
    assert len(result["room"].code) == 6
    assert all(c in "0123456789ABCDEF" for c in result["room"].code)

    assert result["room"].mode == GameMode.SOLO
    assert str(result["room"].status) == "RoomStatus.WAITING"


@pytest.mark.asyncio
async def test_create_room_1v1(usecase, clean_tables):
    result = await usecase.execute(mode=GameMode.ONE_V_ONE)

    assert result["room"] is not None
    assert result["room"].id is not None
    assert result["room"].mode == GameMode.ONE_V_ONE
    assert len(result["room"].code) == 6


@pytest.mark.asyncio
async def test_create_room_unique_codes(usecase, clean_tables):
    result1 = await usecase.execute(mode=GameMode.SOLO)
    result2 = await usecase.execute(mode=GameMode.SOLO)

    assert result1["room"].code != result2["room"].code
    assert result1["room"].id is not None
    assert result2["room"].id is not None
