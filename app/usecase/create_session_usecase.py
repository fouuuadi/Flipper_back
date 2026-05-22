from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from app.domain.ports.session_store import SessionStore
from app.domain.session import Session, SessionStatus


class CreateSessionUseCase:
    """Create an ephemeral game session in Redis (no DB write).

    Generates a UUID session_id and appends a 4-digit suffix to the pseudo
    (e.g. "ABC" → "ABC#4521") to disambiguate users sharing the same initials.
    """

    def __init__(self, session_store: SessionStore):
        self._session_store = session_store

    async def execute(self, pseudo: str, room_code: str | None = None) -> Session:
        formatted_pseudo = f"{pseudo.upper()}#{random.randint(0, 9999):04d}"
        session = Session(
            session_id=uuid.uuid4().hex,
            pseudo=formatted_pseudo,
            score=0,
            status=SessionStatus.WAITING,
            room_code=room_code,
            created_at=datetime.now(timezone.utc),
        )
        await self._session_store.create(session)
        return session
