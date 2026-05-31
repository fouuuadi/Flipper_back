from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.ports.game_event_repository import GameEventRepository
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.player_repository import PlayerRepository
from app.domain.ports.room_repository import RoomRepository


class UnitOfWork(ABC):
    """Atomic boundary spanning the 4 SQL repositories.

    Use cases that touch more than one table (e.g. `StartGameUseCase`
    upserts a player, creates a room, then creates a game) must run
    through a UoW so a mid-flight failure rolls everything back instead
    of leaving orphan rows.

    Usage:

        async with uow:
            player = await uow.players.create(...)
            game = await uow.games.create(player.id, ...)
        # commit on clean exit, rollback on exception
    """

    players: PlayerRepository
    rooms: RoomRepository
    games: GameRepository
    game_events: GameEventRepository

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork":
        ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None:
        ...
