from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.domain.game import GameMode
from app.domain.ports.session_store import SessionStore
from app.domain.pseudo import normalize_and_validate
from app.domain.session import Session, SessionStatus


class CreateSessionUseCase:
    """Create an ephemeral game session in Redis (no DB write).

    The pseudo is normalised via `normalize_and_validate` — case folded to
    upper, with `#HETIC` appended when no hashtag is provided. The resulting
    pseudo is what propagates through Redis, MQTT events, and the eventual DB
    flush in `POST /scores`.
    """

    def __init__(self, session_store: SessionStore):
        self._session_store = session_store

    async def execute(
        self,
        pseudo: str,
        mode: GameMode = GameMode.SOLO,
        room_code: str | None = None,
    ) -> Session:
        normalised_pseudo = normalize_and_validate(pseudo)
        session = Session(
            session_id=uuid.uuid4().hex,
            pseudo=normalised_pseudo,
            score=0,
            status=SessionStatus.WAITING,
            mode=mode,
            room_code=room_code,
            created_at=datetime.now(timezone.utc),
        )
        await self._session_store.create(session)
        return session
