from __future__ import annotations

from app.domain.game import GameMode
from app.domain.leaderboard_entry import LeaderboardEntry
from app.domain.ports.game_repository import GameRepository


class GetLeaderboardUseCase:
    """Renvoie les meilleurs scores terminés, filtrés optionnellement par mode."""

    def __init__(self, game_repository: GameRepository):
        self._repository = game_repository

    async def execute(
        self,
        mode: GameMode | None,
        limit: int,
    ) -> list[LeaderboardEntry]:
        return await self._repository.leaderboard(mode=mode, limit=limit)
