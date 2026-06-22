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
    """Countdown cérémonial d'avant-partie 3 → 2 → 1 → 0, puis `READY` → `PLAYING`.

    Broadcaste `countdown:tick` chaque seconde pour que les 3 apps front
    affichent le même nombre au même instant. Une fois le dernier tick émis,
    la session bascule en `PLAYING` et `match:state: playing` est broadcasté —
    c'est le signal qui rouvre `HandleMqttEventUseCase` aux events score/ball.

    La fonction sleep est injectable pour que les tests unitaires n'aient pas
    à attendre 4 secondes réelles.
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

        # Re-lire la session : un `cmd:abandon` a pu arriver pendant le
        # countdown et basculer le status en OVER — ne pas l'écraser.
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
