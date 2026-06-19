from datetime import datetime, timezone

import pytest

from app.domain.session import Session, SessionStatus
from app.usecase.pause_session_usecase import PauseSessionUseCase


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


def _session(status: SessionStatus = SessionStatus.PLAYING) -> Session:
    return Session(
        session_id="sid",
        pseudo="FOO",
        score=1200,
        lives=2,
        combo=3,
        status=status,
        room_code=None,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_pause_transitions_playing_to_paused_and_broadcasts():
    store = _InMemorySessionStore(_session(SessionStatus.PLAYING))
    broadcaster = _RecordingBroadcaster()

    await PauseSessionUseCase(store, broadcaster).execute("sid")

    persisted = await store.get("sid")
    assert persisted.status == SessionStatus.PAUSED
    # Score/lives/combo preserved
    assert persisted.score == 1200
    assert persisted.lives == 2
    assert persisted.combo == 3
    assert broadcaster.calls == [
        ("sid", {"type": "match:state", "status": "paused", "sessionId": "sid"})
    ]


@pytest.mark.asyncio
async def test_pause_ignored_when_session_not_playing():
    store = _InMemorySessionStore(_session(SessionStatus.WAITING))
    broadcaster = _RecordingBroadcaster()

    await PauseSessionUseCase(store, broadcaster).execute("sid")

    persisted = await store.get("sid")
    assert persisted.status == SessionStatus.WAITING
    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_pause_ignored_when_already_paused():
    store = _InMemorySessionStore(_session(SessionStatus.PAUSED))
    broadcaster = _RecordingBroadcaster()

    await PauseSessionUseCase(store, broadcaster).execute("sid")

    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_pause_unknown_session_is_dropped():
    store = _InMemorySessionStore()  # empty
    broadcaster = _RecordingBroadcaster()

    await PauseSessionUseCase(store, broadcaster).execute("ghost")

    assert broadcaster.calls == []
