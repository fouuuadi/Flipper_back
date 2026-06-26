from abc import ABC, abstractmethod

from app.domain.matchmaking import Matchmaking
from app.domain.player import Player


class MatchmakingRepository(ABC):
    """Port pour la persistence du matchmaking"""

    @abstractmethod
    async def create(self, player_id: int, mode: str) -> Matchmaking:
        """Crée une entrée matchmaking en attente"""
        ...

    @abstractmethod
    async def get_waiting_by_mode(self, mode: str) -> Matchmaking | None:
        """Trouve le premier joueur en attente pour ce mode"""
        ...

    @abstractmethod
    async def find_opponent(self, player_id: int, mode: str) -> Player | None:
        """Cherche un adversaire en attente (excluant le joueur actuel)"""
        ...

    @abstractmethod
    async def claim_waiting_player(self, player_id: int, mode: str) -> Matchmaking | None:
        """Permet à un joueur de revendiquer un joueur en attente pour le mode donné."""
        ...

    @abstractmethod
    async def update_matched(self, matchmaking_id: int, player2_id: int) -> Matchmaking:
        """Met à jour le matchmaking avec le 2e joueur et status=MATCHED"""
        ...

    @abstractmethod
    async def cancel(self, matchmaking_id: int) -> None:
        """Annule une entrée matchmaking avec status=CANCELLED"""
        ...

    @abstractmethod
    async def get_by_id(self, matchmaking_id: int) -> Matchmaking | None:
        """Récupère une entrée matchmaking par ID"""
        ...
