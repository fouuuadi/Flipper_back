from __future__ import annotations

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class Hub:
    def __init__(self):
        self.clients: set[WebSocket] = set()

    async def add(self, ws: WebSocket):
        self.clients.add(ws)

    async def remove(self, ws: WebSocket):
        self.clients.discard(ws)

    async def broadcast(self, data: dict):
        disconnected = []
        for client in self.clients:
            try:
                await client.send_json(data)
            except Exception:
                disconnected.append(client)
        for client in disconnected:
            await self.remove(client)

    def count(self) -> int:
        return len(self.clients)
