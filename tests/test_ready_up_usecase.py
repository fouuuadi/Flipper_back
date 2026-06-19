import asyncio
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


class _RecordingBroadcaster:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        self.calls.append((session_id, message))


def _make_session(**overrides) -> Session:
    base = {
        "session_id": "abc123",
        "pseudo": "FOO",
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
    broadcaster = _RecordingBroadcaster()

    updated = await ReadyUpUseCase(store, broadcaster).execute(session.session_id)

    assert updated.status == SessionStatus.READY
    persisted = await store.get(session.session_id)
    assert persisted.status == SessionStatus.READY


@pytest.mark.asyncio
async def test_ready_up_broadcasts_match_state_ready():
    store = _InMemorySessionStore()
    session = _make_session()
    await store.create(session)
    broadcaster = _RecordingBroadcaster()

    await ReadyUpUseCase(store, broadcaster).execute(session.session_id)

    assert broadcaster.calls == [
        (
            session.session_id,
            {
                "type": "match:state",
                "status": "ready",
                "sessionId": session.session_id,
            },
        )
    ]


@pytest.mark.asyncio
async def test_ready_up_triggers_on_ready_callback_in_background():
    store = _InMemorySessionStore()
    session = _make_session()
    await store.create(session)
    broadcaster = _RecordingBroadcaster()
    invocations: list[str] = []
    done = asyncio.Event()

    async def callback(session_id: str) -> None:
        invocations.append(session_id)
        done.set()

    await ReadyUpUseCase(store, broadcaster, on_ready=callback).execute(session.session_id)

    # The callback runs in a background task — give the event loop a tick.
    await asyncio.wait_for(done.wait(), timeout=1.0)
    assert invocations == [session.session_id]


@pytest.mark.asyncio
async def test_ready_up_raises_when_session_missing():
    store = _InMemorySessionStore()
    broadcaster = _RecordingBroadcaster()

    with pytest.raises(SessionNotFoundError):
        await ReadyUpUseCase(store, broadcaster).execute("unknown")
