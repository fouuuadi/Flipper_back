from __future__ import annotations

from typing import Callable

from app.domain.exceptions import RoomNotFoundError
from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.domain.ports.unit_of_work import UnitOfWork


class StartGameUseCase:
    """Start a game atomically.

    Upserts the player, creates (or joins) the room, creates the game,
    and inserts the `GAME_STARTED` event in a single SQL transaction via
    the injected `UnitOfWork`. Pre-#68 each call hit its own connection,
    so a failure on step 3 (game insert) left orphan player + room rows
    behind.

    The constructor takes a factory (not a UoW instance) because each
    `execute()` call needs its own transaction scope — a UoW is
    one-shot, `async with` opens it and closing commits/rolls back.
    """

    def __init__(self, uow_factory: Callable[[], UnitOfWork]):
        self._uow_factory = uow_factory

    async def execute(
        self,
        pseudo: str,
        mode: GameMode,
        room_code: str | None = None,
    ) -> dict:
        async with self._uow_factory() as uow:
            player = await uow.players.get_by_pseudo(pseudo)
            if not player:
                player = await uow.players.create(pseudo)

            if room_code:
                room = await uow.rooms.get_by_code(room_code)
                if not room:
                    raise RoomNotFoundError(
                        f"Room avec code '{room_code}' n'existe pas"
                    )
            else:
                room = await uow.rooms.create(mode)

            game = await uow.games.create(player.id, room.id, mode)
            event = await uow.game_events.create(game.id, GameEventType.GAME_STARTED)

        return {
            "player": player,
            "room": room,
            "game": game,
            "event": event,
        }
