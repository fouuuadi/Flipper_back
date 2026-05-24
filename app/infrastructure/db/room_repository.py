import uuid

import asyncpg

from app.domain.game import GameMode
from app.domain.ports.room_repository import RoomRepository
from app.domain.room import Room, RoomStatus
from app.infrastructure.db.mappers.room_mapper import row_to_room


class PgRoomRepository(RoomRepository):
    """asyncpg-backed repository for rooms."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def create(self, mode: GameMode) -> Room:
        code = uuid.uuid4().hex[:6].upper()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO rooms (code, mode, status) VALUES ($1, $2, $3) "
                "RETURNING id, code, mode, status, created_at",
                code,
                mode.value,
                RoomStatus.WAITING.value,
            )
        return row_to_room(dict(row))

    async def get_by_id(self, id: int) -> Room | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, code, mode, status, created_at FROM rooms WHERE id = $1",
                id,
            )
        return row_to_room(dict(row) if row is not None else None)

    async def get_by_code(self, code: str) -> Room | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, code, mode, status, created_at FROM rooms WHERE code = $1",
                code,
            )
        return row_to_room(dict(row) if row is not None else None)

    async def get_by_status(self, status: RoomStatus) -> list[Room]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, code, mode, status, created_at FROM rooms "
                "WHERE status = $1 ORDER BY created_at DESC",
                status.value,
            )
        return [row_to_room(dict(r)) for r in rows]
