from datetime import datetime, timezone

import pytest

from app.domain.exceptions import SessionNotFoundError
from app.domain.session import Session, SessionStatus
from app.usecase.ready_up_usecase import ReadyUpUseCase


class _InMemorySessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    async def create(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    async def get(self, session_id: str):
        return self._sessions.get(session_id)

    async def update(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


def _make_session(**overrides) -> Session:
    base = {
        "session_id": "abc123",
        "pseudo": "FOO#0001",
        "score": 0,
        "status": SessionStatus.WAITING,
        "room_code": None,
        "created_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return Session(**base)


@pytest.mark.asyncio
async def test_ready_up_sets_status_to_ready():
    store = _InMemorySessionStore()
    session = _make_session()
    await store.create(session)

    updated = await ReadyUpUseCase(store).execute(session.session_id)

    assert updated.status == SessionStatus.READY
    persisted = await store.get(session.session_id)
    assert persisted.status == SessionStatus.READY


@pytest.mark.asyncio
async def test_ready_up_raises_when_session_missing():
    store = _InMemorySessionStore()

    with pytest.raises(SessionNotFoundError):
        await ReadyUpUseCase(store).execute("unknown")
