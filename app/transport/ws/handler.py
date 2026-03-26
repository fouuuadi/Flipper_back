import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.transport.ws.hub import Hub

logger = logging.getLogger(__name__)

router = APIRouter()

hub = Hub()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    await hub.add(ws)
    logger.info("[ws] connected: clients=%d", hub.count())

    try:
        while True:
            data = await ws.receive_json()

            if "timestamp" not in data or not data["timestamp"]:
                data["timestamp"] = int(time.time() * 1000)

            await hub.broadcast(data)
    except WebSocketDisconnect:
        pass
    finally:
        await hub.remove(ws)
        logger.info("[ws] disconnected: clients=%d", hub.count())
