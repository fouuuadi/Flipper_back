import aiomysql
from app.domain.player import Player


class PlayerRepository:
    """
    Repository pour gérer les opérations CRUD sur les joueurs.
    """

    def __init__(self, pool: aiomysql.Pool):
        """
        Initialise le repository avec un pool de connexions.
        
        Args:
            pool: Pool de connexions aiomysql
        """
        self.pool = pool

    async def create(self, pseudo: str) -> Player:
        """
        Crée un nouveau joueur.
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    await cursor.execute(
                        "INSERT INTO players (pseudo) VALUES (%s)",
                        (pseudo,)
                    )
                    player_id = cursor.lastrowid
                    
                    # Récupérer le joueur créé
                    return await self.get_by_id(player_id)
                except aiomysql.IntegrityError as e:
                    raise ValueError(f"Le pseudo '{pseudo}' est déjà utilisé") from e

    async def get_by_id(self, id: int) -> Player | None:
        """
        Récupère un joueur par son ID.
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, pseudo, created_at FROM players WHERE id = %s",
                    (id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return Player(
                        id=row['id'],
                        pseudo=row['pseudo'],
                        created_at=row['created_at']
                    )
                return None

    async def get_by_pseudo(self, pseudo: str) -> Player | None:
        """
        Récupère un joueur par son pseudo.
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, pseudo, created_at FROM players WHERE pseudo = %s",
                    (pseudo,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return Player(
                        id=row['id'],
                        pseudo=row['pseudo'],
                        created_at=row['created_at']
                    )
                return None
