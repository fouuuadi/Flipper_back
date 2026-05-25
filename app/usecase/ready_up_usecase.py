from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from app.domain.exceptions import SessionNotFoundError
from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster
from app.domain.ports.session_store import SessionStore
from app.domain.session import Session, SessionStatus


class ReadyUpUseCase:
    """Mark a session as `READY` and trigger whatever should follow.

    Broadcasts `match:state: ready` so the 3 front apps know the player
    has confirmed. The optional `on_ready` callback is fired in a
    background `asyncio.Task` — in the real wiring it's the pre-game
    countdown, but it's injected as a plain callable to keep this use
    case unaware of the countdown's existence.
    """

    def __init__(
        self,
        session_store: SessionStore,
        broadcaster: SessionEventBroadcaster,
        on_ready: Callable[[str], Awaitable[None]] | None = None,
    ):
        self._session_store = session_store
        self._broadcaster = broadcaster
        self._on_ready = on_ready

    async def execute(self, session_id: str) -> Session:
        session = await self._session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")

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

        if self._on_ready is not None:
            asyncio.create_task(self._on_ready(session_id))

        return session
