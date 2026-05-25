from __future__ import annotations

import logging

from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster
from app.domain.ports.session_store import SessionStore
from app.domain.session import SessionStatus

logger = logging.getLogger(__name__)

_TERMINATABLE_STATES = (SessionStatus.PLAYING, SessionStatus.PAUSED)


class AbandonSessionUseCase:
    """Transition `PLAYING` or `PAUSED` → `OVER` on `cmd:abandon` (WS).

    This is the **user-initiated** end of a session (the player gave up).
    It only broadcasts `match:state: over` — NOT `game:over`, which is
    reserved for a natural game over triggered by the hardware
    (MQTT `flipper/game/over`).
    """

    def __init__(
        self,
        session_store: SessionStore,
        broadcaster: SessionEventBroadcaster,
    ):
        self._session_store = session_store
        self._broadcaster = broadcaster

    async def execute(self, session_id: str) -> None:
        session = await self._session_store.get(session_id)
        if session is None:
            logger.warning("cmd:abandon on unknown session %s", session_id)
            return
        if session.status not in _TERMINATABLE_STATES:
            logger.warning(
                "cmd:abandon ignored: session %s is %s",
                session_id,
                session.status.value,
            )
            return

        session.status = SessionStatus.OVER
        await self._session_store.update(session)
        await self._broadcaster.broadcast_to_session(
            session_id,
            {
                "type": "match:state",
                "status": session.status.value,
                "sessionId": session_id,
            },
        )
