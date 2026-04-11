import aiomysql
from app.domain.game import Game, GameMode, GameStatus


class GameRepository:
    """
    Repository pour gérer les opérations CRUD sur les games.
    """

    def __init__(self, pool: aiomysql.Pool):
        """
        Initialise le repository avec un pool de connexions.
        """
        self.pool = pool

    async def create(self, player_id: int, mode: GameMode) -> Game:
        """
        Crée une nouvelle game en état PLAYING.
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "INSERT INTO games (player_id, mode, score, status) VALUES (%s, %s, %s, %s)",
                    (player_id, mode.value, 0, GameStatus.PLAYING.value)
                )
                await conn.commit()
                game_id = cursor.lastrowid
                
                # Récupérer la game créée
                return await self.get_by_id(game_id)

    async def get_by_id(self, id: int) -> Game | None:
        """
        Récupère une game par son ID.
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return Game(
                        id=row['id'],
                        match_id=row['match_id'],
                        player_id=row['player_id'],
                        mode=GameMode(row['mode']),
                        score=row['score'],
                        status=GameStatus(row['status']),
                        started_at=row['started_at'],
                        finished_at=row['finished_at']
                    )
                return None