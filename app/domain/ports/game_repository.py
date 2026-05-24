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
        """Top `limit` finished games, best score per player, sorted DESC.

        If `mode` is `None`, consider every mode and take the best score across
        all modes for each player. `rank` is filled by the repo (1-based).
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
        """Atomic flush of a finished Redis session into the DB.

        Inserts (upsert) Player, inserts the Game with status=FINISHED, and
        batch-inserts GameEvents in a single DB transaction. Rolls back on any
        failure.

        Each event dict must carry `topic` (str), `payload` (dict), and
        `occured_at` (ISO-8601 str). Events whose topic is unknown are
        silently skipped.

        Returns `(player_id, game_id, inserted_event_count)`.
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
        """Return finished games for a player, newest first.

        Optionally filter by mode. The list is capped by `limit` and ordered
        by `finished_at DESC`.
        """
        ...
