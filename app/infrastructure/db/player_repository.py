import aiomysql

from app.domain.exceptions import PlayerAlreadyExistsError
from app.domain.player import Player
from app.domain.ports.player_repository import PlayerRepository
from app.infrastructure.db.mappers.player_mapper import row_to_player


class MysqlPlayerRepository(PlayerRepository):
    """
    Repository pour gérer les opérations CRUD sur les joueurs.
    """

    def __init__(self, pool: aiomysql.Pool):
        self.pool = pool

    async def create(self, pseudo: str) -> Player:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(
                        "INSERT INTO players (pseudo) VALUES (%s)",
                        (pseudo,),
                    )
                    player_id = cursor.lastrowid
                    await conn.commit()
                except aiomysql.IntegrityError as e:
                    raise PlayerAlreadyExistsError(
                        f"Le pseudo '{pseudo}' est déjà utilisé"
                    ) from e

            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, pseudo, created_at FROM players WHERE id = %s",
                    (player_id,),
                )
                return row_to_player(await cursor.fetchone())

    async def get_by_id(self, id: int) -> Player | None:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, pseudo, created_at FROM players WHERE id = %s",
                    (id,),
                )
                return row_to_player(await cursor.fetchone())

    async def get_by_pseudo(self, pseudo: str) -> Player | None:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, pseudo, created_at FROM players WHERE pseudo = %s",
                    (pseudo,),
                )
                return row_to_player(await cursor.fetchone())
