from __future__ import annotations

from app.domain.game import GameMode
from app.domain.leaderboard_entry import LeaderboardEntry
from app.domain.ports.game_repository import GameRepository


class GetLeaderboardUseCase:
    """Return the top finished scores, optionally filtered by mode."""

    def __init__(self, game_repository: GameRepository):
        self._repository = game_repository

    async def execute(
        self,
        mode: GameMode | None,
        limit: int,
    ) -> list[LeaderboardEntry]:
        return await self._repository.leaderboard(mode=mode, limit=limit)
