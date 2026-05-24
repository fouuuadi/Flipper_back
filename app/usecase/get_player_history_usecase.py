from __future__ import annotations

from app.domain.exceptions import PlayerNotFoundError
from app.domain.game import Game, GameMode
from app.domain.player import Player
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.player_repository import PlayerRepository


class GetPlayerHistoryUseCase:
    """Read-only history of finished games for a given player_id.

    The use case first checks the player exists (so callers can distinguish
    "no games yet" from "this player does not exist") then fetches the
    finished games filtered by the optional mode.
    """

    def __init__(
        self,
        player_repository: PlayerRepository,
        game_repository: GameRepository,
    ):
        self._player_repository = player_repository
        self._game_repository = game_repository

    async def execute(
        self,
        player_id: int,
        mode: GameMode | None,
        limit: int,
    ) -> tuple[Player, list[Game]]:
        player = await self._player_repository.get_by_id(player_id)
        if player is None:
            raise PlayerNotFoundError(f"Player with id {player_id} not found")
        games = await self._game_repository.get_finished_games_by_player(
            player_id=player_id,
            mode=mode,
            limit=limit,
        )
        return player, games
