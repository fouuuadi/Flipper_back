import aiomysql

from app.domain.game import Game, GameMode, GameStatus
from app.domain.ports.game_repository import GameRepository
from app.infrastructure.db.mappers.game_mapper import row_to_game


class MysqlGameRepository(GameRepository):
    """
    Repository pour gérer les opérations CRUD sur les games.
    """

    def __init__(self, pool: aiomysql.Pool):
        self.pool = pool

    async def create(self, player_id: int, room_id: int | None, mode: GameMode) -> Game:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO games (player_id, room_id, mode, score, status) VALUES (%s, %s, %s, %s, %s)",
                    (player_id, room_id, mode.value, 0, GameStatus.PLAYING.value),
                )
                game_id = cursor.lastrowid
                await conn.commit()

            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (game_id,),
                )
                return row_to_game(await cursor.fetchone())

    async def get_by_id(self, id: int) -> Game | None:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (id,),
                )
                return row_to_game(await cursor.fetchone())

    async def add_points(self, game_id: int, points: int) -> Game:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE games SET score = score + %s WHERE id = %s",
                    (points, game_id),
                )
                await conn.commit()

            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (game_id,),
                )
                return row_to_game(await cursor.fetchone())

    async def get_active_by_room(self, room_id: int) -> list[Game]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE room_id = %s AND status = %s",
                    (room_id, GameStatus.PLAYING.value),
                )
                rows = await cursor.fetchall()
                return [row_to_game(row) for row in rows]

    async def finish(self, game_id: int) -> Game:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE games SET status = %s, finished_at = NOW() WHERE id = %s",
                    (GameStatus.FINISHED.value, game_id),
                )
                await conn.commit()

            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (game_id,),
                )
                return row_to_game(await cursor.fetchone())

    async def get_by_status(self, status: GameStatus) -> list[Game]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE status = %s ORDER BY started_at DESC",
                    (status.value,),
                )
                rows = await cursor.fetchall()
                return [row_to_game(row) for row in rows]
