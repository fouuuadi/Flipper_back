from app.domain.matchmaking import Matchmaking, MatchmakingStatus
from app.domain.player import Player
from app.domain.exceptions import MatchmakingNotFoundError
from app.domain.ports.matchmaking_repository import MatchmakingRepository
from app.infrastructure.db._executor import Executor, acquire
from app.infrastructure.db.mappers.matchmaking_mapper import row_to_matchmaking
from app.infrastructure.db.mappers.player_mapper import row_to_player


class PgMatchmakingRepository(MatchmakingRepository):

    def __init__(self, executor: Executor):
        self._executor = executor

    async def create(self, player_id: int, mode: str) -> Matchmaking:
        """Crée une entrée matchmaking en attente"""
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                """INSERT INTO matchmaking (player1_id, status, mode) 
                   VALUES ($1, $2, $3) 
                   RETURNING id, player1_id, player2_id, status, mode, created_at""",
                player_id,
                MatchmakingStatus.WAITING.value,
                mode,
            )
        return row_to_matchmaking(dict(row))

    async def get_waiting_by_mode(self, mode: str) -> Matchmaking | None:
        """Trouve le premier joueur en attente pour ce mode"""
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                """SELECT id, player1_id, player2_id, status, mode, created_at 
                   FROM matchmaking 
                   WHERE status = $1 AND mode = $2 
                   ORDER BY created_at ASC 
                   LIMIT 1""",
                MatchmakingStatus.WAITING.value,
                mode,
            )
        return row_to_matchmaking(dict(row) if row is not None else None)

    async def find_opponent(self, player_id: int, mode: str) -> Player | None:
        """Cherche un adversaire en attente"""
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                """SELECT p.id, p.pseudo, p.created_at 
                   FROM matchmaking m 
                   JOIN players p ON m.player1_id = p.id 
                   WHERE m.status = $1 AND m.mode = $2 AND p.id != $3 
                   ORDER BY m.created_at ASC 
                   LIMIT 1""",
                MatchmakingStatus.WAITING.value,
                mode,
                player_id,
            )
        return row_to_player(dict(row) if row is not None else None)

    async def update_matched(self, matchmaking_id: int, player2_id: int) -> Matchmaking:
        """Met à jour le matchmaking avec le 2e joueur et status=MATCHED"""
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                """UPDATE matchmaking 
                   SET player2_id = $1, status = $2 
                   WHERE id = $3 
                   RETURNING id, player1_id, player2_id, status, mode, created_at""",
                player2_id,
                MatchmakingStatus.MATCHED.value,
                matchmaking_id,
            )
        if row is None:
            raise MatchmakingNotFoundError(f"Matchmaking {matchmaking_id} not found")
        return row_to_matchmaking(dict(row))

    async def cancel(self, matchmaking_id: int) -> None:
        """Annule une entrée matchmaking (status=CANCELLED)"""
        async with acquire(self._executor) as conn:
            await conn.execute(
                """UPDATE matchmaking 
                   SET status = $1 
                   WHERE id = $2""",
                MatchmakingStatus.CANCELLED.value,
                matchmaking_id,
            )

    async def get_by_id(self, matchmaking_id: int) -> Matchmaking | None:
        """Récupère une entrée matchmaking par ID"""
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                """SELECT id, player1_id, player2_id, status, mode, created_at 
                   FROM matchmaking 
                   WHERE id = $1""",
                matchmaking_id,
            )
        return row_to_matchmaking(dict(row) if row is not None else None)
    
    
    async def claim_waiting_player(
        self,
        player_id: int,
        mode: str,
    ) -> Matchmaking | None:
        """
        Récupère et verrouille atomiquement
        un joueur WAITING disponible.
        Utilise SELECT FOR UPDATE pour éviter les race conditions.
        """
        async with acquire(self._executor) as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """SELECT id, player1_id, player2_id, status, mode, created_at 
                       FROM matchmaking 
                       WHERE status = $1 AND mode = $2 AND player1_id != $3
                       ORDER BY created_at ASC 
                       LIMIT 1
                       FOR UPDATE""",
                    MatchmakingStatus.WAITING.value,
                    mode,
                    player_id,
                )
                
                if row is None:
                    return None
                
                # Update with player2_id and status=MATCHED
                updated_row = await conn.fetchrow(
                    """UPDATE matchmaking 
                       SET player2_id = $1, status = $2 
                       WHERE id = $3 
                       RETURNING id, player1_id, player2_id, status, mode, created_at""",
                    player_id,
                    MatchmakingStatus.MATCHED.value,
                    row['id'],
                )
                return row_to_matchmaking(dict(updated_row))
