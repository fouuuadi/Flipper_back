from __future__ import annotations

import logging

from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster
from app.domain.ports.session_store import SessionStore
from app.domain.session import SessionStatus

logger = logging.getLogger(__name__)


class PauseSessionUseCase:
    """Transition `PLAYING` → `PAUSED` on `cmd:pause` (WS).

    During `PAUSED`, `HandleMqttEventUseCase` silently drops score/ball
    events so the player can step away without their idle hardware
    polluting the score.
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
            logger.warning("cmd:pause on unknown session %s", session_id)
            return
        if session.status is not SessionStatus.PLAYING:
            logger.warning(
                "cmd:pause ignored: session %s is %s",
                session_id,
                session.status.value,
            )
            return

        session.status = SessionStatus.PAUSED
        await self._session_store.update(session)
        await self._broadcaster.broadcast_to_session(
            session_id,
            {
                "type": "match:state",
                "status": session.status.value,
                "sessionId": session_id,
            },
        )
