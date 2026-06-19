from datetime import datetime, timezone

import pytest

from app.domain.session import Session, SessionStatus
from app.usecase.start_countdown_usecase import (
    COUNTDOWN_VALUES,
    StartCountdownUseCase,
)


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


async def _instant_sleep(_seconds: float) -> None:
    """Replacement for asyncio.sleep so tests don't actually wait."""
    return None


def _ready_session() -> Session:
    return Session(
        session_id="sid",
        pseudo="FOO",
        score=0,
        lives=3,
        combo=0,
        status=SessionStatus.READY,
        room_code=None,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_countdown_emits_ticks_in_order_then_match_state_playing():
    store = _InMemorySessionStore(_ready_session())
    broadcaster = _RecordingBroadcaster()

    await StartCountdownUseCase(store, broadcaster, sleep=_instant_sleep).execute("sid")

    # 4 countdown ticks (3, 2, 1, 0) + 1 match:state: playing
    assert len(broadcaster.calls) == len(COUNTDOWN_VALUES) + 1

    tick_messages = broadcaster.calls[:-1]
    final_message = broadcaster.calls[-1]

    assert [msg["value"] for _, msg in tick_messages] == list(COUNTDOWN_VALUES)
    assert all(msg["type"] == "countdown:tick" for _, msg in tick_messages)

    assert final_message == (
        "sid",
        {"type": "match:state", "status": "playing", "sessionId": "sid"},
    )

    # Session is now PLAYING.
    persisted = await store.get("sid")
    assert persisted.status == SessionStatus.PLAYING


@pytest.mark.asyncio
async def test_countdown_calls_sleep_between_each_tick():
    store = _InMemorySessionStore(_ready_session())
    broadcaster = _RecordingBroadcaster()
    sleep_calls: list[float] = []

    async def recording_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    await StartCountdownUseCase(
        store, broadcaster, sleep=recording_sleep
    ).execute("sid")

    # One sleep per tick (4 ticks → 4 sleeps).
    assert len(sleep_calls) == len(COUNTDOWN_VALUES)
    assert all(s == 1.0 for s in sleep_calls)


@pytest.mark.asyncio
async def test_countdown_does_not_overwrite_over_status():
    """If `cmd:abandon` arrived during the countdown and flipped status to
    OVER, the final transition to PLAYING must be skipped."""
    session = _ready_session()
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()

    # Mutate the session mid-flight: switch to OVER right before the last
    # update — easier: a sleep callback that mutates the stored session.
    async def sleep_then_abandon(_seconds: float) -> None:
        s = await store.get("sid")
        if s is not None:
            s.status = SessionStatus.OVER
            await store.update(s)

    await StartCountdownUseCase(
        store, broadcaster, sleep=sleep_then_abandon
    ).execute("sid")

    persisted = await store.get("sid")
    assert persisted.status == SessionStatus.OVER

    # No final match:state: playing should have been broadcast.
    types = [msg["type"] for _, msg in broadcaster.calls]
    assert "match:state" not in types


@pytest.mark.asyncio
async def test_countdown_handles_session_disappearing_mid_flight():
    store = _InMemorySessionStore(_ready_session())
    broadcaster = _RecordingBroadcaster()

    async def sleep_then_delete(_seconds: float) -> None:
        await store.delete("sid")

    # Should not raise even if session is gone.
    await StartCountdownUseCase(
        store, broadcaster, sleep=sleep_then_delete
    ).execute("sid")

    # 4 ticks broadcasted but no final match:state.
    types = [msg["type"] for _, msg in broadcaster.calls]
    assert types.count("countdown:tick") == len(COUNTDOWN_VALUES)
    assert "match:state" not in types
