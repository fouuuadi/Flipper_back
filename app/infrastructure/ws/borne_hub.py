"""WebSocket hub de la borne.

Calqué sur `session_hub`, mais le canal est **permanent** et indexé par
`borne_id` : les 3 écrans (playfield / backglass / dmd) s'y connectent au boot
et reçoivent l'état partagé (navigation + match) broadcasté par le backend.

`BorneHubManager` implémente `SessionEventBroadcaster` : son
`broadcast_to_session(...)` **ignore le session_id** et diffuse sur la borne.
Ça permet de réutiliser tels quels les use cases de cycle de match (ReadyUp,
Pause, StartCountdown, HandleMqttEvent…) en leur injectant ce broadcaster, sans
les modifier.
"""
from __future__ import annotations

import logging
from typing import Dict, List

from fastapi import WebSocket

from app.domain.ports.borne_event_broadcaster import BorneEventBroadcaster

logger = logging.getLogger(__name__)


class BorneHub:
    def __init__(self, borne_id: str):
        self.borne_id = borne_id
        self.clients: List[WebSocket] = []

    async def add_client(self, websocket: WebSocket) -> None:
        self.clients.append(websocket)

    async def remove_client(self, websocket: WebSocket) -> None:
        if websocket in self.clients:
            self.clients.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        for client in self.clients:
            try:
                await client.send_json(message)
            except Exception:
                logger.exception("WS send failed for borne %s", self.borne_id)


class BorneHubManager(BorneEventBroadcaster):
    def __init__(self):
        self._hubs: Dict[str, BorneHub] = {}

    def get_or_create(self, borne_id: str) -> BorneHub:
        if borne_id not in self._hubs:
            self._hubs[borne_id] = BorneHub(borne_id)
        return self._hubs[borne_id]

    def get(self, borne_id: str) -> BorneHub | None:
        return self._hubs.get(borne_id)

    async def broadcast_to_borne(self, borne_id: str, message: dict) -> None:
        hub = self.get(borne_id)
        if hub:
            await hub.broadcast(message)

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        """Shim `SessionEventBroadcaster`.

        Il n'y a qu'une borne active : on ignore le `session_id` et on diffuse à
        tous les écrans des borne(s) connue(s). Permet aux use cases de match
        d'émettre sur le bus borne sans aucune modification.
        """
        for hub in self._hubs.values():
            await hub.broadcast(message)


borne_hub_manager = BorneHubManager()
