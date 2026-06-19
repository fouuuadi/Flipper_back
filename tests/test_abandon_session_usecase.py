from datetime import datetime, timezone

import pytest

from app.domain.session import Session, SessionStatus
from app.usecase.abandon_session_usecase import AbandonSessionUseCase


class _InMemorySessionStore:
    def __init__(self, session: Session | None = None):
        self._sessions: dict[str, Session] = {}
        if session is not None:
            self._sessions[session.session_id] = session

    async def create(self, session): self._sessions[session.session_id] = session
    async def get(self, session_id): return self._sessions.get(session_id)
    async def update(self, session): self._sessions[session.session_id] = session
    async def delete(self, session_id): self._sessions.pop(session_id, None)


class _RecordingBroadcaster:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        self.calls.append((session_id, message))


def _session(status: SessionStatus) -> Session:
    return Session(
        session_id="sid",
        pseudo="FOO",
        score=900,
        lives=1,
        combo=0,
        status=status,
        room_code=None,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_abandon_from_playing_transitions_to_over_and_broadcasts_match_state():
    store = _InMemorySessionStore(_session(SessionStatus.PLAYING))
    broadcaster = _RecordingBroadcaster()

    await AbandonSessionUseCase(store, broadcaster).execute("sid")

    persisted = await store.get("sid")
    assert persisted.status == SessionStatus.OVER
    # Important: only match:state — NOT game:over (that's the natural one)
    assert broadcaster.calls == [
        ("sid", {"type": "match:state", "status": "over", "sessionId": "sid"})
    ]
    # No "game:over" message should be present.
    assert all(msg.get("type") != "game:over" for _, msg in broadcaster.calls)


@pytest.mark.asyncio
async def test_abandon_from_paused_also_transitions_to_over():
    store = _InMemorySessionStore(_session(SessionStatus.PAUSED))
    broadcaster = _RecordingBroadcaster()

    await AbandonSessionUseCase(store, broadcaster).execute("sid")

    persisted = await store.get("sid")
    assert persisted.status == SessionStatus.OVER
    assert broadcaster.calls == [
        ("sid", {"type": "match:state", "status": "over", "sessionId": "sid"})
    ]


@pytest.mark.asyncio
async def test_abandon_ignored_when_session_waiting():
    store = _InMemorySessionStore(_session(SessionStatus.WAITING))
    broadcaster = _RecordingBroadcaster()

    await AbandonSessionUseCase(store, broadcaster).execute("sid")

    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_abandon_ignored_when_already_over():
    store = _InMemorySessionStore(_session(SessionStatus.OVER))
    broadcaster = _RecordingBroadcaster()

    await AbandonSessionUseCase(store, broadcaster).execute("sid")

    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_abandon_unknown_session_is_dropped():
    store = _InMemorySessionStore()
    broadcaster = _RecordingBroadcaster()

    await AbandonSessionUseCase(store, broadcaster).execute("ghost")

    assert broadcaster.calls == []
