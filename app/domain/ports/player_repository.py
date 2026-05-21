from abc import ABC, abstractmethod

from app.domain.player import Player


class PlayerRepository(ABC):
    @abstractmethod
    async def create(self, pseudo: str) -> Player:
        ...

    @abstractmethod
    async def get_by_id(self, id: int) -> Player | None:
        ...

    @abstractmethod
    async def get_by_pseudo(self, pseudo: str) -> Player | None:
        ...
