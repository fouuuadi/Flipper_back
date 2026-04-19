import aiomysql
from app.domain.game_event import GameEvent, GameEventType


class GameEventRepository:
    """
    Repository pour gérer les opérations CRUD sur les game events.
    """

    def __init__(self, pool: aiomysql.Pool):
        """
        Initialise le repository avec un pool de connexions.
        """
        self.pool = pool

    async def create(self, game_id: int, type: GameEventType, points: int = 0) -> GameEvent:
        """
        Crée un nouvel événement de game.
        """
        async with self.pool.acquire() as conn:
            # INSERT avec curseur normal (pas DictCursor)
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO game_events (game_id, type, points) VALUES (%s, %s, %s)",
                    (game_id, type.value, points)
                )
                event_id = cursor.lastrowid
                await conn.commit()
            
            # SELECT avec DictCursor
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, game_id, type, points, occured_at FROM game_events WHERE id = %s",
                    (event_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return GameEvent(
                        id=row['id'],
                        game_id=row['game_id'],
                        type=GameEventType(row['type']),
                        points=row['points'],
                        occured_at=row['occured_at']
                    )
                return None

    async def get_by_id(self, id: int) -> GameEvent | None:
        """
        Récupère un événement par son ID.
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, game_id, type, points, occured_at FROM game_events WHERE id = %s",
                    (id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return GameEvent(
                        id=row['id'],
                        game_id=row['game_id'],
                        type=GameEventType(row['type']),
                        points=row['points'],
                        occured_at=row['occured_at']
                    )
                return None