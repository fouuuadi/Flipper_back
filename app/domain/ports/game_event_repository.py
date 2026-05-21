from abc import ABC, abstractmethod

from app.domain.game_event import GameEvent, GameEventType


class GameEventRepository(ABC):
    @abstractmethod
    async def create(self, game_id: int, type: GameEventType, points: int = 0) -> GameEvent:
        ...

    @abstractmethod
    async def get_by_id(self, id: int) -> GameEvent | None:
        ...

    @abstractmethod
    async def get_by_game_id(self, game_id: int, limit: int = 10) -> list[GameEvent]:
        ...
