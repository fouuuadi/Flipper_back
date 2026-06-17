from abc import ABC, abstractmethod


class SessionService(ABC):
    @abstractmethod
    async def check_pseudo_uniqueness_in_room(self, room_code: str, pseudo: str) -> bool:
        """Retourne True si le pseudo est disponible dans la room, False s'il est déjà pris."""
        ...
