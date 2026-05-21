import uuid

import aiomysql

from app.domain.game import GameMode
from app.domain.ports.room_repository import RoomRepository
from app.domain.room import Room, RoomStatus
from app.infrastructure.db.mappers.room_mapper import row_to_room


class MysqlRoomRepository(RoomRepository):
    """
    Repository pour gérer les opérations CRUD sur les rooms.
    """

    def __init__(self, pool: aiomysql.Pool):
        self.pool = pool

    async def create(self, mode: GameMode) -> Room:
        code = uuid.uuid4().hex[:6].upper()

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO rooms (code, mode, status) VALUES (%s, %s, %s)",
                    (code, mode.value, RoomStatus.WAITING.value),
                )
                room_id = cursor.lastrowid
                await conn.commit()

            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, code, mode, status, created_at FROM rooms WHERE id = %s",
                    (room_id,),
                )
                return row_to_room(await cursor.fetchone())

    async def get_by_id(self, id: int) -> Room | None:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, code, mode, status, created_at FROM rooms WHERE id = %s",
                    (id,),
                )
                return row_to_room(await cursor.fetchone())

    async def get_by_code(self, code: str) -> Room | None:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, code, mode, status, created_at FROM rooms WHERE code = %s",
                    (code,),
                )
                return row_to_room(await cursor.fetchone())
