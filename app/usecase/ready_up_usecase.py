from __future__ import annotations

from app.domain.exceptions import SessionNotFoundError
from app.domain.ports.session_store import SessionStore
from app.domain.session import Session, SessionStatus


class ReadyUpUseCase:
    """Mark an ephemeral session as ready in Redis.

    The "all players ready → broadcast game:start" logic is deferred to the
    MQTT bridge step (#87), where WS broadcasting is wired in.
    """

    def __init__(self, session_store: SessionStore):
        self._session_store = session_store

    async def execute(self, session_id: str) -> Session:
        session = await self._session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")

        session.status = SessionStatus.READY
        await self._session_store.update(session)
        return session
