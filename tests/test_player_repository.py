import pytest
import pytest_asyncio

from app.domain.exceptions import PlayerAlreadyExistsError
from app.infrastructure.db.player_repository import PgPlayerRepository


@pytest_asyncio.fixture
async def repository(db_pool):
    return PgPlayerRepository(db_pool)


@pytest.mark.asyncio
async def test_create_and_get_by_id(repository, clean_tables):
    player = await repository.create("alice")

    assert player.id is not None
    assert player.pseudo == "alice"
    assert player.created_at is not None

    retrieved = await repository.get_by_id(player.id)

    assert retrieved is not None
    assert retrieved.id == player.id
    assert retrieved.pseudo == "alice"


@pytest.mark.asyncio
async def test_create_and_get_by_pseudo(repository, clean_tables):
    created = await repository.create("bob")

    retrieved = await repository.get_by_pseudo("bob")

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.pseudo == "bob"
    assert retrieved.created_at is not None


@pytest.mark.asyncio
async def test_duplicate_pseudo_raises_error(repository, clean_tables):
    await repository.create("charlie")
    with pytest.raises(PlayerAlreadyExistsError, match="déjà utilisé"):
        await repository.create("charlie")


@pytest.mark.asyncio
async def test_get_nonexistent_player(repository, clean_tables):
    assert await repository.get_by_id(999) is None
    assert await repository.get_by_pseudo("nonexistent") is None


@pytest.mark.asyncio
async def test_multiple_players(repository, clean_tables):
    p1 = await repository.create("player1")
    p2 = await repository.create("player2")
    p3 = await repository.create("player3")

    assert p1.id != p2.id != p3.id
    assert (await repository.get_by_id(p1.id)).pseudo == "player1"
    assert (await repository.get_by_id(p2.id)).pseudo == "player2"
    assert (await repository.get_by_id(p3.id)).pseudo == "player3"
