from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.domain.game import Game, GameMode, GameStatus
from app.domain.leaderboard_entry import LeaderboardEntry


class GameRepository(ABC):
    @abstractmethod
    async def create(self, player_id: int, room_id: int | None, mode: GameMode) -> Game:
        ...

    @abstractmethod
    async def leaderboard(
        self,
        mode: GameMode | None,
        limit: int,
    ) -> list[LeaderboardEntry]:
        """Les `limit` meilleures parties terminées, meilleur score par joueur, triées DESC.

        Si `mode` vaut `None`, on considère tous les modes et on prend le
        meilleur score tous modes confondus pour chaque joueur. `rank` est
        rempli par le repo (commence à 1).
        """
        ...

    @abstractmethod
    async def persist_finished_session(
        self,
        pseudo: str,
        mode: GameMode,
        score: int,
        started_at: datetime,
        finished_at: datetime,
        events: list[dict[str, Any]],
    ) -> tuple[int, int, int]:
        """Flush atomique d'une session Redis terminée vers la base.

        Insère (upsert) le Player, insère le Game avec status=FINISHED, et
        insère les GameEvents en batch dans une seule transaction. Rollback
        en cas d'échec.

        Chaque dict d'event doit porter `topic` (str), `payload` (dict) et
        `occured_at` (str ISO-8601). Les events dont le topic est inconnu sont
        ignorés silencieusement.

        Renvoie `(player_id, game_id, inserted_event_count)`.
        """
        ...

    @abstractmethod
    async def get_by_id(self, id: int) -> Game | None:
        ...

    @abstractmethod
    async def add_points(self, game_id: int, points: int) -> Game:
        ...

    @abstractmethod
    async def get_active_by_room(self, room_id: int) -> list[Game]:
        ...

    @abstractmethod
    async def finish(self, game_id: int) -> Game:
        ...

    @abstractmethod
    async def get_by_status(self, status: GameStatus) -> list[Game]:
        ...

    @abstractmethod
    async def get_finished_games_by_player(
        self,
        player_id: int,
        mode: GameMode | None,
        limit: int,
    ) -> list[Game]:
        """Renvoie les parties terminées d'un joueur, les plus récentes d'abord.

        Filtre optionnel par mode. La liste est plafonnée par `limit` et
        ordonnée par `finished_at DESC`.
        """
        ...

    @abstractmethod
    async def get_best_solo_score(self, player_id: int) -> int | None:
        """Renvoie le meilleur score solo persisté pour ce joueur, ou None.

        Ne considère que les parties avec `status='finished'` et `mode='solo'`.
        Utilisé par la règle "le meilleur score gagne" appliquée dans
        `POST /scores`.
        """
        ...
