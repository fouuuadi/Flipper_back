from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.ports.game_event_repository import GameEventRepository
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.player_repository import PlayerRepository
from app.domain.ports.room_repository import RoomRepository


class UnitOfWork(ABC):
    """Frontière atomique couvrant les 4 repositories SQL.

    Les use cases qui touchent plus d'une table (ex. `StartGameUseCase`
    upsert un player, crée une room, puis crée un game) doivent passer par
    un UoW pour qu'un échec en cours de route rollback tout au lieu de
    laisser des lignes orphelines.

    Usage :

        async with uow:
            player = await uow.players.create(...)
            game = await uow.games.create(player.id, ...)
        # commit en sortie propre, rollback en cas d'exception
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
