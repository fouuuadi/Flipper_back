import uuid

from app.domain.game import GameMode
from app.domain.ports.room_repository import RoomRepository
from app.domain.room import Room, RoomStatus
from app.infrastructure.db._executor import Executor, acquire
from app.infrastructure.db.mappers.room_mapper import row_to_room


class PgRoomRepository(RoomRepository):
    """Repository des rooms, sur asyncpg (SQL brut, pas d'ORM).

    Accepte soit un `asyncpg.Pool`, soit une `asyncpg.Connection` quand on tourne
    dans une `UnitOfWork` (pour partager la transaction).
    """

    def __init__(self, executor: Executor):
        self._executor = executor

    async def create(self, mode: GameMode) -> Room:
        # Code court et lisible (6 caractères hexa en majuscules) tiré d'un UUID v4.
        # La colonne `code` est UNIQUE en base : une collision (très improbable sur
        # 6 hexa) ferait remonter une erreur d'insertion plutôt qu'un doublon muet.
        code = uuid.uuid4().hex[:6].upper()
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                "INSERT INTO rooms (code, mode, status) VALUES ($1, $2, $3) "
                "RETURNING id, code, mode, status, created_at",
                code,
                mode.value,
                RoomStatus.WAITING.value,
            )
        return row_to_room(dict(row))

    async def get_by_id(self, id: int) -> Room | None:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                "SELECT id, code, mode, status, created_at FROM rooms WHERE id = $1",
                id,
            )
        return row_to_room(dict(row) if row is not None else None)

    async def get_by_code(self, code: str) -> Room | None:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                "SELECT id, code, mode, status, created_at FROM rooms WHERE code = $1",
                code,
            )
        return row_to_room(dict(row) if row is not None else None)

    async def get_by_status(self, status: RoomStatus) -> list[Room]:
        async with acquire(self._executor) as conn:
            rows = await conn.fetch(
                "SELECT id, code, mode, status, created_at FROM rooms "
                "WHERE status = $1 ORDER BY created_at DESC",
                status.value,
            )
        return [row_to_room(dict(r)) for r in rows]
