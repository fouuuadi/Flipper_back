import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app import di
from app.infrastructure.ws.room_hub import hub_manager
from app.infrastructure.ws.session_hub import session_hub_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_subscribe(
    websocket: WebSocket,
    room_repository=Depends(di.get_room_repo),
    session_store=Depends(di.get_session_store),
):
    """Subscribe to game events.

    Pick exactly one of:
    - `?session_id=...` — receive only events for that session (MQTT → Redis → WS)
    - `?room_code=...` — receive everything broadcast for that room (legacy room flow)
    """
    session_id = websocket.query_params.get("session_id")
    room_code = websocket.query_params.get("room_code")

    if session_id and room_code:
        await websocket.close(code=1000, reason="provide session_id OR room_code, not both")
        return

    if session_id:
        await _serve_session(websocket, session_id, session_store)
        return

    if room_code:
        await _serve_room(websocket, room_code, room_repository)
        return

    await websocket.close(code=1000, reason="session_id or room_code required")


async def _serve_session(websocket: WebSocket, session_id: str, session_store) -> None:
    session = await session_store.get(session_id)
    if session is None:
        await websocket.close(code=1000, reason="session not found")
        return

    await websocket.accept()
    logger.info("[ws] connected to session %s", session_id)

    hub = session_hub_manager.get_or_create(session_id)
    await hub.add_client(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.remove_client(websocket)
        logger.info("[ws] disconnected from session %s", session_id)


async def _serve_room(websocket: WebSocket, room_code: str, room_repository) -> None:
    room = await room_repository.get_by_code(room_code)
    if not room:
        await websocket.close(code=1000, reason="room not found")
        return

    await websocket.accept()
    logger.info("[ws] connected to room %s", room_code)

    hub = hub_manager.get_or_create_room_hub(room_code)
    await hub.add_client(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.remove_client(websocket)
        logger.info("[ws] disconnected from room %s", room_code)
