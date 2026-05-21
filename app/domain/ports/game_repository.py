from abc import ABC, abstractmethod

from app.domain.game import Game, GameMode


class GameRepository(ABC):
    @abstractmethod
    async def create(self, player_id: int, room_id: int | None, mode: GameMode) -> Game:
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
