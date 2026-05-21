import aiomysql

from app.domain.game_event import GameEvent, GameEventType
from app.domain.ports.game_event_repository import GameEventRepository
from app.infrastructure.db.mappers.game_event_mapper import row_to_game_event


class MysqlGameEventRepository(GameEventRepository):
    """
    Repository pour gérer les opérations CRUD sur les game events.
    """

    def __init__(self, pool: aiomysql.Pool):
        self.pool = pool

    async def create(self, game_id: int, type: GameEventType, points: int = 0) -> GameEvent:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO game_events (game_id, type, points) VALUES (%s, %s, %s)",
                    (game_id, type.value, points),
                )
                event_id = cursor.lastrowid
                await conn.commit()

            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, game_id, type, points, occured_at FROM game_events WHERE id = %s",
                    (event_id,),
                )
                return row_to_game_event(await cursor.fetchone())

    async def get_by_id(self, id: int) -> GameEvent | None:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, game_id, type, points, occured_at FROM game_events WHERE id = %s",
                    (id,),
                )
                return row_to_game_event(await cursor.fetchone())

    async def get_by_game_id(self, game_id: int, limit: int = 10) -> list[GameEvent]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, game_id, type, points, occured_at FROM game_events WHERE game_id = %s ORDER BY occured_at DESC, id DESC LIMIT %s",
                    (game_id, limit),
                )
                rows = await cursor.fetchall()
                return [row_to_game_event(row) for row in rows]
