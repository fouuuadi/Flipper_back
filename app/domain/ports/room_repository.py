from abc import ABC, abstractmethod

from app.domain.game import GameMode
from app.domain.room import Room


class RoomRepository(ABC):
    @abstractmethod
    async def create(self, mode: GameMode) -> Room:
        ...

    @abstractmethod
    async def get_by_id(self, id: int) -> Room | None:
        ...

    @abstractmethod
    async def get_by_code(self, code: str) -> Room | None:
        ...
