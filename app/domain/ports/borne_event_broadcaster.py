from abc import ABC, abstractmethod

from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster


class BorneEventBroadcaster(SessionEventBroadcaster, ABC):
    """Diffuse un message à tous les écrans d'une borne.

    Étend `SessionEventBroadcaster` : une implémentation borne sait diffuser à la
    fois via `broadcast_to_borne` (navigation) et via `broadcast_to_session`
    (réutilisé par les use cases de match, qui ignorent le canal concret).
    """

    @abstractmethod
    async def broadcast_to_borne(self, borne_id: str, message: dict) -> None: ...
