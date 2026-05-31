import asyncpg

from app.domain.exceptions import PlayerAlreadyExistsError
from app.domain.player import Player
from app.domain.ports.player_repository import PlayerRepository
from app.infrastructure.db._executor import Executor, acquire
from app.infrastructure.db.mappers.player_mapper import row_to_player


class PgPlayerRepository(PlayerRepository):
    """asyncpg-backed repository for players.

    Accepts either an `asyncpg.Pool` (standalone, default) or a single
    `asyncpg.Connection` (when running inside a `UnitOfWork`).
    """

    def __init__(self, executor: Executor):
        self._executor = executor

    async def create(self, pseudo: str) -> Player:
        try:
            async with acquire(self._executor) as conn:
                row = await conn.fetchrow(
                    "INSERT INTO players (pseudo) VALUES ($1) "
                    "RETURNING id, pseudo, created_at",
                    pseudo,
                )
        except asyncpg.UniqueViolationError as e:
            raise PlayerAlreadyExistsError(
                f"Le pseudo '{pseudo}' est déjà utilisé"
            ) from e
        return row_to_player(dict(row))

    async def get_by_id(self, id: int) -> Player | None:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                "SELECT id, pseudo, created_at FROM players WHERE id = $1",
                id,
            )
        return row_to_player(dict(row) if row is not None else None)

    async def get_by_pseudo(self, pseudo: str) -> Player | None:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                "SELECT id, pseudo, created_at FROM players WHERE pseudo = $1",
                pseudo,
            )
        return row_to_player(dict(row) if row is not None else None)
