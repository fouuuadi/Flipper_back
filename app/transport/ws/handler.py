import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app import di
from app.domain.ports.borne_store import BorneStore
from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster
from app.domain.ports.session_store import SessionStore
from app.usecase.abandon_session_usecase import AbandonSessionUseCase
from app.usecase.apply_borne_intent_usecase import ApplyBorneIntentUseCase
from app.usecase.pause_session_usecase import PauseSessionUseCase
from app.usecase.resume_session_usecase import ResumeSessionUseCase
from app.usecase.start_countdown_usecase import StartCountdownUseCase

logger = logging.getLogger(__name__)

router = APIRouter()

_CMD_PAUSE = "cmd:pause"
_CMD_RESUME = "cmd:resume"
_CMD_ABANDON = "cmd:abandon"
_MSG_INTENT = "intent"


@router.websocket("/ws")
async def websocket_subscribe(
    websocket: WebSocket,
    room_repository=Depends(di.get_room_repo),
    session_store: SessionStore = Depends(di.get_session_store),
    session_hub_manager=Depends(di.get_session_hub_manager),
    room_hub_manager=Depends(di.get_hub_manager),
    borne_store: BorneStore = Depends(di.get_borne_store),
    borne_hub_manager=Depends(di.get_borne_hub_manager),
    expected_borne_id: str = Depends(di.get_borne_id),
):
    """Subscribe to game events.

    Pick exactly one of:
    - `?borne_id=...` — join the permanent borne bus (the 3 screens). Receive
      the shared navigation + match state, and send `intent` / `cmd:*` messages.
    - `?session_id=...` — receive events for that session, and send
      `cmd:pause` / `cmd:resume` / `cmd:abandon` to drive the session
      lifecycle (MATCH_SYNC protocol).
    - `?room_code=...` — receive everything broadcast for that room
      (legacy room flow, read-only).
    """
    session_id = websocket.query_params.get("session_id")
    room_code = websocket.query_params.get("room_code")
    borne_id = websocket.query_params.get("borne_id")

    provided = [p for p in (session_id, room_code, borne_id) if p]
    if len(provided) > 1:
        await websocket.close(
            code=1000, reason="provide exactly one of borne_id, session_id, room_code"
        )
        return

    if borne_id:
        await _serve_borne(
            websocket,
            borne_id,
            expected_borne_id,
            borne_store,
            borne_hub_manager,
            session_store,
        )
        return

    if session_id:
        await _serve_session(websocket, session_id, session_store, session_hub_manager)
        return

    if room_code:
        await _serve_room(websocket, room_code, room_repository, room_hub_manager)
        return

    await websocket.close(code=1000, reason="borne_id, session_id or room_code required")


async def _serve_borne(
    websocket: WebSocket,
    borne_id: str,
    expected_borne_id: str,
    borne_store: BorneStore,
    borne_hub_manager,
    session_store: SessionStore,
) -> None:
    if borne_id != expected_borne_id:
        await websocket.close(code=1000, reason="unknown borne_id")
        return

    await websocket.accept()
    logger.info("[ws] connected to borne %s", borne_id)

    hub = borne_hub_manager.get_or_create(borne_id)
    await hub.add_client(websocket)

    # Snapshot à la connexion : un écran qui (re)démarre doit afficher l'état
    # courant immédiatement, sans attendre le prochain broadcast.
    borne = await borne_store.get_or_create(borne_id)
    await websocket.send_json(
        {
            "type": "nav:state",
            "nav": borne.nav.value,
            "sessionId": borne.active_session_id,
        }
    )

    apply_intent = ApplyBorneIntentUseCase(borne_store, borne_hub_manager, session_store)

    try:
        while True:
            raw = await websocket.receive_text()
            await _handle_borne_intent(raw, borne_id, apply_intent)
    except WebSocketDisconnect:
        await hub.remove_client(websocket)
        logger.info("[ws] disconnected from borne %s", borne_id)


async def _handle_borne_intent(
    raw: str,
    borne_id: str,
    apply_intent: ApplyBorneIntentUseCase,
) -> None:
    """Parse a borne message and route it.

    Handles `{"type": "intent", "action": ...}` (navigation) and the match
    controls `cmd:pause` / `cmd:resume` / `cmd:abandon` (which drive the borne's
    active session). Malformed messages are logged and dropped.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[ws] borne %s sent invalid JSON: %r", borne_id, raw[:120])
        return

    if not isinstance(payload, dict):
        logger.warning("[ws] borne %s sent non-object payload: %r", borne_id, payload)
        return

    msg_type = payload.get("type")

    if msg_type == _MSG_INTENT:
        action = payload.get("action")
        if not isinstance(action, str):
            logger.warning(
                "[ws] borne %s intent without a string action: %r", borne_id, payload
            )
            return
        await apply_intent.execute(borne_id, action, payload.get("payload"))
    elif msg_type in (_CMD_PAUSE, _CMD_RESUME, _CMD_ABANDON):
        await apply_intent.handle_match_command(borne_id, msg_type)
    else:
        logger.warning("[ws] borne %s sent unknown message type %r", borne_id, msg_type)


async def _serve_session(
    websocket: WebSocket,
    session_id: str,
    session_store: SessionStore,
    session_hub_manager,
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
            await _handle_session_command(raw, session_id, session_store, session_hub_manager)
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
        countdown = StartCountdownUseCase(session_store, broadcaster)
        await ResumeSessionUseCase(
            session_store, broadcaster, start_countdown=countdown.execute
        ).execute(session_id)
    elif cmd_type == _CMD_ABANDON:
        await AbandonSessionUseCase(session_store, broadcaster).execute(session_id)
    else:
        logger.warning(
            "[ws] session %s sent unknown cmd type %r",
            session_id,
            cmd_type,
        )


async def _serve_room(
    websocket: WebSocket, room_code: str, room_repository, room_hub_manager
) -> None:
    room = await room_repository.get_by_code(room_code)
    if not room:
        await websocket.close(code=1000, reason="room not found")
        return

    await websocket.accept()
    logger.info("[ws] connected to room %s", room_code)

    hub = room_hub_manager.get_or_create_room_hub(room_code)
    await hub.add_client(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.remove_client(websocket)
        logger.info("[ws] disconnected from room %s", room_code)
