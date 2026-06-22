"""Tests d'intégration pour `PgUnitOfWork`.

On tape sur le vrai pool Postgres pour valider le comportement *atomique* :
une sortie propre commit, une exception rollback, et les 4 repositories
partagent une seule connexion pendant le bloc.
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.infrastructure.db.unit_of_work import PgUnitOfWork


@pytest_asyncio.fixture
async def make_uow(db_pool):
    def _factory():
        return PgUnitOfWork(db_pool)
    return _factory


@pytest.mark.asyncio
async def test_uow_commits_on_clean_exit(make_uow, db_pool, clean_tables):
    """Après un `async with` propre, toutes les écritures sont visibles à l'extérieur."""
    async with make_uow() as uow:
        player = await uow.players.create("alice")
        room = await uow.rooms.create(GameMode.SOLO)
        game = await uow.games.create(player.id, room.id, GameMode.SOLO)
        await uow.game_events.create(game.id, GameEventType.GAME_STARTED)

    async with db_pool.acquire() as conn:
        n_players = await conn.fetchval("SELECT COUNT(*) FROM players")
        n_rooms = await conn.fetchval("SELECT COUNT(*) FROM rooms")
        n_games = await conn.fetchval("SELECT COUNT(*) FROM games")
        n_events = await conn.fetchval("SELECT COUNT(*) FROM game_events")

    assert (n_players, n_rooms, n_games, n_events) == (1, 1, 1, 1)


@pytest.mark.asyncio
async def test_uow_rolls_back_on_exception_no_orphan_rows(
    make_uow, db_pool, clean_tables
):
    """Si quoi que ce soit lève en pleine transaction, rien n'est persisté.

    C'est exactement le bug corrigé par #68 : avant l'UoW, `StartGameUseCase`
    faisait 4 appels de connexion séparés. Un échec au 3e appel laissait
    derrière lui des lignes player + room orphelines.
    """
    class _Boom(Exception):
        pass

    with pytest.raises(_Boom):
        async with make_uow() as uow:
            await uow.players.create("bob")
            await uow.rooms.create(GameMode.SOLO)
            raise _Boom()

    async with db_pool.acquire() as conn:
        n_players = await conn.fetchval("SELECT COUNT(*) FROM players")
        n_rooms = await conn.fetchval("SELECT COUNT(*) FROM rooms")
    assert (n_players, n_rooms) == (0, 0)


@pytest.mark.asyncio
async def test_uow_repos_share_the_same_connection(make_uow, clean_tables):
    """Les 4 repos exposés par l'UoW doivent tous être liés à la même conn —
    sinon ils ne pourraient pas tenir dans la même transaction SQL."""
    async with make_uow() as uow:
        assert uow.players._executor is uow.rooms._executor
        assert uow.rooms._executor is uow.games._executor
        assert uow.games._executor is uow.game_events._executor


@pytest.mark.asyncio
async def test_uow_uncommitted_writes_invisible_to_outside_pool(
    make_uow, db_pool, clean_tables
):
    """En pleine transaction, une nouvelle connexion du pool ne doit pas voir l'écriture."""
    async with make_uow() as uow:
        await uow.players.create("carol")

        async with db_pool.acquire() as outside_conn:
            n = await outside_conn.fetchval(
                "SELECT COUNT(*) FROM players WHERE pseudo = $1", "carol"
            )
        assert n == 0  # toujours pas commité

    # Après le commit, c'est visible.
    async with db_pool.acquire() as outside_conn:
        n = await outside_conn.fetchval(
            "SELECT COUNT(*) FROM players WHERE pseudo = $1", "carol"
        )
    assert n == 1
