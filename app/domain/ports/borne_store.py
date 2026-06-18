from abc import ABC, abstractmethod

from app.domain.borne import Borne


class BorneStore(ABC):
    @abstractmethod
    async def get_or_create(self, borne_id: str) -> Borne:
        """Retourne la borne existante, ou la crée (nav=splash) au premier accès."""
        ...

    @abstractmethod
    async def update(self, borne: Borne) -> None:
        ...
