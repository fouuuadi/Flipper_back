import aiomysql
import uuid
from app.domain.room import Room, RoomStatus
from app.domain.game import GameMode


class RoomRepository:
    """
    Repository pour gérer les opérations CRUD sur les rooms.
    Utilise aiomysql pour les requêtes async.
    """

    def __init__(self, pool: aiomysql.Pool):

        self.pool = pool

    async def create(self, mode: GameMode) -> Room:
        """
        Crée une nouvelle room avec un code unique généré.
        
        Args:
            mode: Mode de jeu (SOLO ou 1v1)
            
        Returns:
            Room créée avec son ID et son code
        """
        code = uuid.uuid4().hex[:6].upper()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "INSERT INTO rooms (code, mode, status) VALUES (%s, %s, %s)",
                    (code, mode.value, RoomStatus.WAITING.value)
                )
                await conn.commit()
                room_id = cursor.lastrowid
                
                # Récupérer la room créée
                return await self.get_by_id(room_id)

    async def get_by_id(self, id: int) -> Room | None:
        """
        Récupère une room par son ID.
        
            
        Returns:
            Room trouvée ou None
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
            
        Returns:
            Room trouvée ou None
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