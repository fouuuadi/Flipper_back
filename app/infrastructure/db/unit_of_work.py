from __future__ import annotations

import asyncpg

from app.domain.ports.unit_of_work import UnitOfWork
from app.infrastructure.db.game_event_repository import PgGameEventRepository
from app.infrastructure.db.game_repository import PgGameRepository
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository


class PgUnitOfWork(UnitOfWork):
    """Postgres Unit of Work.

    `__aenter__` acquires a connection from the pool and opens a
    transaction; the 4 repositories are bound to that same connection so
    every statement runs inside the same transaction. `__aexit__`
    commits on clean exit, rolls back on exception, and releases the
    connection back to the pool either way.
    """

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool
        self._conn: asyncpg.Connection | None = None
        self._tx: asyncpg.connection.transaction.Transaction | None = None

    async def __aenter__(self) -> "PgUnitOfWork":
        self._conn = await self._pool.acquire()
        self._tx = self._conn.transaction()
        await self._tx.start()

        self.players = PgPlayerRepository(self._conn)
        self.rooms = PgRoomRepository(self._conn)
        self.games = PgGameRepository(self._conn)
        self.game_events = PgGameEventRepository(self._conn)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                await self._tx.commit()
            else:
                await self._tx.rollback()
        finally:
            if self._conn is not None:
                await self._pool.release(self._conn)
            self._conn = None
            self._tx = None
