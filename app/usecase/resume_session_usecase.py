from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster
from app.domain.ports.session_store import SessionStore
from app.domain.session import SessionStatus

logger = logging.getLogger(__name__)


class ResumeSessionUseCase:
    """Transition `PAUSED` → `READY` → `PLAYING` avec un countdown 3-2-1-GO.

    Avant #111, le resume sautait directement de `PAUSED` à `PLAYING`, ce qui
    était brutal côté UX. Désormais le use case rejoue le même countdown
    cérémonial que le démarrage initial : il bascule le status en `READY`,
    broadcaste `match:state: ready`, puis lance `StartCountdownUseCase` dans
    une background task (même pattern que `ReadyUpUseCase`). Le countdown gère
    lui-même la transition finale `READY → PLAYING`.

    Le score, les vies et le combo sont préservés pendant la pause — seul le
    status change.

    Le callback `start_countdown` est injecté pour que ce use case reste
    ignorant de l'existence du countdown. Il est optionnel pour que les tests
    unitaires puissent isoler la moitié `PAUSED → READY` indépendamment.
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

        # PAUSED → READY (phase de countdown). Pendant READY,
        # HandleMqttEventUseCase continue de droper les events score/ball
        # grâce à son guard `status != PLAYING` existant.
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

        # La transition finale READY → PLAYING est gérée par le countdown.
        if self._start_countdown is not None:
            asyncio.create_task(self._start_countdown(session_id))
