from __future__ import annotations

from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster


class CompositeBroadcaster(SessionEventBroadcaster):
    """Diffuse un même message via plusieurs broadcasters.

    Utilisé pour les events MQTT pendant la migration : on émet à la fois sur le
    hub de session (front legacy connecté en `?session_id`) et sur le hub borne
    (les 3 écrans connectés en `?borne_id`). Une fois le front migré, on pourra
    ne garder que le broadcaster borne.
    """

    def __init__(self, *broadcasters: SessionEventBroadcaster):
        self._broadcasters = broadcasters

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        for broadcaster in self._broadcasters:
            await broadcaster.broadcast_to_session(session_id, message)
