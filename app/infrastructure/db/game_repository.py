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

    async def create(self, player_id: int, room_id: int | None, mode: GameMode) -> Game:
        """
        Crée une nouvelle game en état PLAYING.
        """
        async with self.pool.acquire() as conn:
            # INSERT avec curseur normal (pas DictCursor)
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO games (player_id, room_id, mode, score, status) VALUES (%s, %s, %s, %s, %s)",
                    (player_id, room_id, mode.value, 0, GameStatus.PLAYING.value)
                )
                game_id = cursor.lastrowid
                await conn.commit()
            
            # SELECT avec DictCursor
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (game_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return Game(
                        id=row['id'],
                        match_id=row['match_id'],
                        player_id=row['player_id'],
                        room_id=row['room_id'],
                        mode=GameMode(row['mode']),
                        score=row['score'],
                        status=GameStatus(row['status']),
                        started_at=row['started_at'],
                        finished_at=row['finished_at']
                    )
                return None

    async def get_by_id(self, id: int) -> Game | None:
        """
        Récupère une game par son ID.
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return Game(
                        id=row['id'],
                        match_id=row['match_id'],
                        player_id=row['player_id'],
                        room_id=row['room_id'],
                        mode=GameMode(row['mode']),
                        score=row['score'],
                        status=GameStatus(row['status']),
                        started_at=row['started_at'],
                        finished_at=row['finished_at']
                    )
                return None

    async def add_points(self, game_id: int, points: int) -> Game:
        """
        Ajoute des points au score d'une game.
        """
        async with self.pool.acquire() as conn:
            # UPDATE avec curseur normal
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE games SET score = score + %s WHERE id = %s",
                    (points, game_id)
                )
                await conn.commit()
            
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (game_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return Game(
                        id=row['id'],
                        match_id=row['match_id'],
                        player_id=row['player_id'],
                        room_id=row['room_id'],
                        mode=GameMode(row['mode']),
                        score=row['score'],
                        status=GameStatus(row['status']),
                        started_at=row['started_at'],
                        finished_at=row['finished_at']
                    )
                return None

    async def get_active_by_room(self, room_id: int) -> list[Game]:
        """
        Récupère toutes les games actives (PLAYING) d'une room.
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE room_id = %s AND status = %s",
                    (room_id, GameStatus.PLAYING.value)
                )
                rows = await cursor.fetchall()
                
                games = []
                for row in rows:
                    games.append(Game(
                        id=row['id'],
                        match_id=row['match_id'],
                        player_id=row['player_id'],
                        room_id=row['room_id'],
                        mode=GameMode(row['mode']),
                        score=row['score'],
                        status=GameStatus(row['status']),
                        started_at=row['started_at'],
                        finished_at=row['finished_at']
                    ))
                return games