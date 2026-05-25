from datetime import datetime, timezone

import pytest

from app.domain.session import Session, SessionStatus
from app.usecase.resume_session_usecase import ResumeSessionUseCase


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


def _session(status: SessionStatus = SessionStatus.PAUSED) -> Session:
    return Session(
        session_id="sid",
        pseudo="FOO#0001",
        score=4200,
        lives=1,
        combo=5,
        status=status,
        room_code=None,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_resume_transitions_paused_to_playing_and_broadcasts():
    store = _InMemorySessionStore(_session(SessionStatus.PAUSED))
    broadcaster = _RecordingBroadcaster()

    await ResumeSessionUseCase(store, broadcaster).execute("sid")

    persisted = await store.get("sid")
    assert persisted.status == SessionStatus.PLAYING
    # Score/lives/combo preserved across pause/resume.
    assert persisted.score == 4200
    assert persisted.lives == 1
    assert persisted.combo == 5
    assert broadcaster.calls == [
        ("sid", {"type": "match:state", "status": "playing", "sessionId": "sid"})
    ]


@pytest.mark.asyncio
async def test_resume_ignored_when_session_already_playing():
    store = _InMemorySessionStore(_session(SessionStatus.PLAYING))
    broadcaster = _RecordingBroadcaster()

    await ResumeSessionUseCase(store, broadcaster).execute("sid")

    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_resume_ignored_when_session_waiting():
    store = _InMemorySessionStore(_session(SessionStatus.WAITING))
    broadcaster = _RecordingBroadcaster()

    await ResumeSessionUseCase(store, broadcaster).execute("sid")

    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_resume_unknown_session_is_dropped():
    store = _InMemorySessionStore()
    broadcaster = _RecordingBroadcaster()

    await ResumeSessionUseCase(store, broadcaster).execute("ghost")

    assert broadcaster.calls == []
