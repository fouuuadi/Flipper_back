import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app import di
from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster
from app.domain.ports.session_store import SessionStore
from app.infrastructure.ws.room_hub import hub_manager
from app.infrastructure.ws.session_hub import session_hub_manager
from app.usecase.abandon_session_usecase import AbandonSessionUseCase
from app.usecase.pause_session_usecase import PauseSessionUseCase
from app.usecase.resume_session_usecase import ResumeSessionUseCase

logger = logging.getLogger(__name__)

router = APIRouter()

_CMD_PAUSE = "cmd:pause"
_CMD_RESUME = "cmd:resume"
_CMD_ABANDON = "cmd:abandon"


@router.websocket("/ws")
async def websocket_subscribe(
    websocket: WebSocket,
    room_repository=Depends(di.get_room_repo),
    session_store: SessionStore = Depends(di.get_session_store),
):
    """Subscribe to game events.

    Pick exactly one of:
    - `?session_id=...` — receive events for that session, and send
      `cmd:pause` / `cmd:resume` / `cmd:abandon` to drive the session
      lifecycle (MATCH_SYNC protocol).
    - `?room_code=...` — receive everything broadcast for that room
      (legacy room flow, read-only).
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


async def _serve_session(
    websocket: WebSocket, session_id: str, session_store: SessionStore
) -> None:
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
            raw = await websocket.receive_text()
            await _handle_session_command(raw, session_id, session_store, hub)
    except WebSocketDisconnect:
        await hub.remove_client(websocket)
        logger.info("[ws] disconnected from session %s", session_id)


async def _handle_session_command(
    raw: str,
    session_id: str,
    session_store: SessionStore,
    broadcaster: SessionEventBroadcaster,
) -> None:
    """Parse a `cmd:*` JSON payload from the client and route it to the
    matching use case. Malformed messages are logged and dropped silently.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(
            "[ws] session %s sent invalid JSON: %r",
            session_id,
            raw[:120],
        )
        return

    if not isinstance(payload, dict):
        logger.warning(
            "[ws] session %s sent non-object payload: %r",
            session_id,
            payload,
        )
        return

    cmd_type = payload.get("type")

    if cmd_type == _CMD_PAUSE:
        await PauseSessionUseCase(session_store, broadcaster).execute(session_id)
    elif cmd_type == _CMD_RESUME:
        await ResumeSessionUseCase(session_store, broadcaster).execute(session_id)
    elif cmd_type == _CMD_ABANDON:
        await AbandonSessionUseCase(session_store, broadcaster).execute(session_id)
    else:
        logger.warning(
            "[ws] session %s sent unknown cmd type %r",
            session_id,
            cmd_type,
        )


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
