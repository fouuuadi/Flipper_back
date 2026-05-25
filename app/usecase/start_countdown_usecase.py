from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster
from app.domain.ports.session_store import SessionStore
from app.domain.session import SessionStatus

logger = logging.getLogger(__name__)

COUNTDOWN_VALUES = (3, 2, 1, 0)
COUNTDOWN_TICK_INTERVAL_SECONDS = 1.0


class StartCountdownUseCase:
    """Pre-game ceremonial countdown 3 → 2 → 1 → 0, then `READY` → `PLAYING`.

    Broadcasts `countdown:tick` every second so the 3 front apps display
    the same number at the same moment. Once the final tick is emitted,
    the session is flipped to `PLAYING` and `match:state: playing` is
    broadcast — that's the signal that gates `HandleMqttEventUseCase`
    back open for score/ball events.

    The sleep function is injectable so unit tests don't have to wait
    4 real seconds.
    """

    def __init__(
        self,
        session_store: SessionStore,
        broadcaster: SessionEventBroadcaster,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._session_store = session_store
        self._broadcaster = broadcaster
        self._sleep = sleep

    async def execute(self, session_id: str) -> None:
        for value in COUNTDOWN_VALUES:
            await self._broadcaster.broadcast_to_session(
                session_id,
                {"type": "countdown:tick", "value": value},
            )
            await self._sleep(COUNTDOWN_TICK_INTERVAL_SECONDS)

        # Re-read the session: a `cmd:abandon` may have arrived during the
        # countdown and flipped status to OVER — don't overwrite that.
        session = await self._session_store.get(session_id)
        if session is None:
            logger.info(
                "countdown: session %s disappeared before reaching PLAYING",
                session_id,
            )
            return
        if session.status is not SessionStatus.READY:
            logger.info(
                "countdown: session %s left READY mid-countdown (now %s), skipping transition",
                session_id,
                session.status.value,
            )
            return

        session.status = SessionStatus.PLAYING
        await self._session_store.update(session)
        await self._broadcaster.broadcast_to_session(
            session_id,
            {
                "type": "match:state",
                "status": session.status.value,
                "sessionId": session_id,
            },
        )
