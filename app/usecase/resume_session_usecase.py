from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster
from app.domain.ports.session_store import SessionStore
from app.domain.session import SessionStatus

logger = logging.getLogger(__name__)


class ResumeSessionUseCase:
    """Transition `PAUSED` → `READY` → `PLAYING` with a 3-2-1-GO countdown.

    Pre-#111 the resume jumped straight from `PAUSED` to `PLAYING`, which
    felt brutal UX-wise. Now the use case re-enters the same ceremonial
    countdown as the initial start: it flips the status to `READY`,
    broadcasts `match:state: ready`, then fires `StartCountdownUseCase`
    in a background task (same pattern as `ReadyUpUseCase`). The
    countdown handles the final `READY → PLAYING` transition itself.

    Score, lives and combo are preserved across the pause — only the
    status changes.

    The `start_countdown` callback is injected so this use case stays
    unaware of the countdown's existence. It's optional so unit tests
    can isolate the `PAUSED → READY` half independently.
    """

    def __init__(
        self,
        session_store: SessionStore,
        broadcaster: SessionEventBroadcaster,
        start_countdown: Callable[[str], Awaitable[None]] | None = None,
    ):
        self._session_store = session_store
        self._broadcaster = broadcaster
        self._start_countdown = start_countdown

    async def execute(self, session_id: str) -> None:
        session = await self._session_store.get(session_id)
        if session is None:
            logger.warning("cmd:resume on unknown session %s", session_id)
            return
        if session.status is not SessionStatus.PAUSED:
            logger.warning(
                "cmd:resume ignored: session %s is %s",
                session_id,
                session.status.value,
            )
            return

        # PAUSED → READY (countdown phase). During READY,
        # HandleMqttEventUseCase keeps dropping score/ball events thanks
        # to its existing `status != PLAYING` guard.
        session.status = SessionStatus.READY
        await self._session_store.update(session)
        await self._broadcaster.broadcast_to_session(
            session_id,
            {
                "type": "match:state",
                "status": session.status.value,
                "sessionId": session_id,
            },
        )

        # Final READY → PLAYING transition is owned by the countdown.
        if self._start_countdown is not None:
            asyncio.create_task(self._start_countdown(session_id))
