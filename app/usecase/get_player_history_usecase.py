from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import PlayerNotFoundError
from app.domain.game import Game, GameMode
from app.domain.player import Player
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.player_repository import PlayerRepository


@dataclass
class PlayerHistoryItem:
    """A Game from the player history, paired with the `is_best` flag.

    `is_best` is `True` for the solo game whose score equals the player's
    best solo score. It stays `False` for every 1v1 game (the notion of
    personal record is meaningless when scores are tied to a match).
    """

    game: Game
    is_best: bool


class GetPlayerHistoryUseCase:
    """Read-only history of finished games for a given player_id.

    The use case first checks the player exists (so callers can distinguish
    "no games yet" from "this player does not exist") then fetches the
    finished games filtered by the optional mode and flags the personal best
    solo game in the returned list.
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
    ) -> tuple[Player, list[PlayerHistoryItem]]:
        player = await self._player_repository.get_by_id(player_id)
        if player is None:
            raise PlayerNotFoundError(f"Player with id {player_id} not found")
        games = await self._game_repository.get_finished_games_by_player(
            player_id=player_id,
            mode=mode,
            limit=limit,
        )
        best_solo_score = await self._game_repository.get_best_solo_score(player_id)
        items = [self._flag(game, best_solo_score) for game in games]
        return player, items

    @staticmethod
    def _flag(game: Game, best_solo_score: int | None) -> PlayerHistoryItem:
        is_best = (
            game.mode is GameMode.SOLO
            and best_solo_score is not None
            and game.score == best_solo_score
        )
        return PlayerHistoryItem(game=game, is_best=is_best)
