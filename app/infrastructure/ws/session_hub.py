"""WebSocket hub indexed by session_id.

Unlike `room_hub`, which groups all clients of a room together, here each
session has its own hub — events broadcast on `flipper/.../{sessionId}` reach
only the player whose flipper produced them.
"""
from __future__ import annotations

import logging
from typing import Dict, List

from fastapi import WebSocket

from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster

logger = logging.getLogger(__name__)


class SessionHub:
    def __init__(self, session_id: str):
        self.session_id = session_id
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
                logger.exception(
                    "WS send failed for session %s", self.session_id
                )


class SessionHubManager(SessionEventBroadcaster):
    def __init__(self):
        self._hubs: Dict[str, SessionHub] = {}

    def get_or_create(self, session_id: str) -> SessionHub:
        if session_id not in self._hubs:
            self._hubs[session_id] = SessionHub(session_id)
        return self._hubs[session_id]

    def get(self, session_id: str) -> SessionHub | None:
        return self._hubs.get(session_id)

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        hub = self.get(session_id)
        if hub:
            await hub.broadcast(message)


session_hub_manager = SessionHubManager()
