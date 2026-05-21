import aiomysql
import uuid
from app.domain.room import Room, RoomStatus
from app.domain.game import GameMode
from app.domain.ports.room_repository import RoomRepository


class MysqlRoomRepository(RoomRepository):
    """
    Repository pour gérer les opérations CRUD sur les rooms.
    """

    def __init__(self, pool: aiomysql.Pool):

        self.pool = pool

    async def create(self, mode: GameMode) -> Room:
        """
        Crée une nouvelle room avec un code unique généré.
        """
        code = uuid.uuid4().hex[:6].upper()
        
        async with self.pool.acquire() as conn:
            # INSERT avec curseur normal (pas DictCursor)
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO rooms (code, mode, status) VALUES (%s, %s, %s)",
                    (code, mode.value, RoomStatus.WAITING.value)
                )
                room_id = cursor.lastrowid
                await conn.commit()
            
            # SELECT avec DictCursor
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, code, mode, status, created_at FROM rooms WHERE id = %s",
                    (room_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return Room(
                        id=row['id'],
                        code=row['code'],
                        mode=GameMode(row['mode']),
                        status=RoomStatus(row['status']),
                        created_at=row['created_at']
                    )
                return None

    async def get_by_id(self, id: int) -> Room | None:
        """
        Récupère une room par son ID.
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, code, mode, status, created_at FROM rooms WHERE id = %s",
                    (id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return Room(
                        id=row['id'],
                        code=row['code'],
                        mode=GameMode(row['mode']),
                        status=RoomStatus(row['status']),
                        created_at=row['created_at']
                    )
                return None

    async def get_by_code(self, code: str) -> Room | None:
        """
        Récupère une room par son code.
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, code, mode, status, created_at FROM rooms WHERE code = %s",
                    (code,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return Room(
                        id=row['id'],
                        code=row['code'],
                        mode=GameMode(row['mode']),
                        status=RoomStatus(row['status']),
                        created_at=row['created_at']
                    )
                return None