from __future__ import annotations

from app.domain.exceptions import PlayerNotFoundError
from app.domain.player import Player
from app.domain.ports.player_repository import PlayerRepository
from app.domain.pseudo import normalize_and_validate


class GetPlayerUseCase:
    """Read-only lookup, by id or by (normalised) pseudo."""

    def __init__(self, player_repository: PlayerRepository):
        self._repository = player_repository

    async def execute_by_id(self, player_id: int) -> Player:
        player = await self._repository.get_by_id(player_id)
        if player is None:
            raise PlayerNotFoundError(f"Player with id {player_id} not found")
        return player

    async def execute_by_pseudo(self, raw_pseudo: str) -> Player:
        pseudo = normalize_and_validate(raw_pseudo)
        player = await self._repository.get_by_pseudo(pseudo)
        if player is None:
            raise PlayerNotFoundError(f"Player {pseudo!r} not found")
        return player
