from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import PlayerNotFoundError
from app.domain.game import Game, GameMode
from app.domain.player import Player
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.player_repository import PlayerRepository


@dataclass
class PlayerHistoryItem:
    """Un Game de l'historique du joueur, accompagné du flag `is_best`.

    `is_best` vaut `True` pour la partie solo dont le score est égal au meilleur
    score solo du joueur. Il reste `False` pour toute partie 1v1 (la notion de
    record personnel n'a pas de sens quand les scores sont liés à un match).
    """

    game: Game
    is_best: bool


class GetPlayerHistoryUseCase:
    """Historique en lecture seule des parties terminées pour un player_id donné.

    Le use case vérifie d'abord que le joueur existe (pour que les appelants
    puissent distinguer "aucune partie encore" de "ce joueur n'existe pas"),
    puis récupère les parties terminées filtrées par le mode optionnel et marque
    la meilleure partie solo dans la liste renvoyée.
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
