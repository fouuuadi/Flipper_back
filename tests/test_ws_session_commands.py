"""Unit tests for the WS session command router (`_handle_session_command`).

The function lives in `app/transport/ws/handler.py` and routes JSON
`cmd:*` payloads received over the WebSocket to the right use case.
Tests cover routing, malformed input, and pass-through of unknown types.
"""
import asyncio
from datetime import datetime, timezone

import pytest

from app.domain.session import Session, SessionStatus
from app.transport.ws.handler import _handle_session_command


async def _cancel_pending_tasks() -> None:
    """`cmd:resume` launches a real-time countdown via `asyncio.create_task`.
    Cancel any leftover background task so it doesn't bleed into other tests.
    """
    pending = [
        t
        for t in asyncio.all_tasks()
        if t is not asyncio.current_task() and not t.done()
    ]
    for t in pending:
        t.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


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
        score=100,
        lives=2,
        combo=1,
        status=status,
        room_code=None,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_cmd_pause_routes_to_pause_use_case():
    store = _InMemorySessionStore(_session(SessionStatus.PLAYING))
    broadcaster = _RecordingBroadcaster()

    await _handle_session_command(
        '{"type":"cmd:pause"}', "sid", store, broadcaster
    )

    assert (await store.get("sid")).status == SessionStatus.PAUSED
    assert broadcaster.calls == [
        ("sid", {"type": "match:state", "status": "paused", "sessionId": "sid"})
    ]


@pytest.mark.asyncio
async def test_cmd_resume_routes_to_resume_use_case_and_triggers_countdown():
    store = _InMemorySessionStore(_session(SessionStatus.PAUSED))
    broadcaster = _RecordingBroadcaster()

    await _handle_session_command(
        '{"type":"cmd:resume"}', "sid", store, broadcaster
    )

    # `cmd:resume` flips the session to READY immediately and broadcasts
    # match:state: ready. The READY → PLAYING transition is the countdown's
    # job and runs in a background task (covered by
    # tests/test_resume_session_usecase.py with a mocked sleep).
    assert (await store.get("sid")).status == SessionStatus.READY
    assert broadcaster.calls == [
        ("sid", {"type": "match:state", "status": "ready", "sessionId": "sid"})
    ]

    await _cancel_pending_tasks()


@pytest.mark.asyncio
async def test_cmd_abandon_routes_to_abandon_use_case():
    store = _InMemorySessionStore(_session(SessionStatus.PLAYING))
    broadcaster = _RecordingBroadcaster()

    await _handle_session_command(
        '{"type":"cmd:abandon"}', "sid", store, broadcaster
    )

    assert (await store.get("sid")).status == SessionStatus.OVER
    assert broadcaster.calls == [
        ("sid", {"type": "match:state", "status": "over", "sessionId": "sid"})
    ]


@pytest.mark.asyncio
async def test_malformed_json_is_dropped_silently():
    store = _InMemorySessionStore(_session(SessionStatus.PLAYING))
    broadcaster = _RecordingBroadcaster()

    await _handle_session_command(
        "not a json", "sid", store, broadcaster
    )

    assert (await store.get("sid")).status == SessionStatus.PLAYING
    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_non_object_payload_is_dropped_silently():
    store = _InMemorySessionStore(_session(SessionStatus.PLAYING))
    broadcaster = _RecordingBroadcaster()

    await _handle_session_command("[1,2,3]", "sid", store, broadcaster)

    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_unknown_cmd_type_is_dropped_silently():
    store = _InMemorySessionStore(_session(SessionStatus.PLAYING))
    broadcaster = _RecordingBroadcaster()

    await _handle_session_command(
        '{"type":"cmd:nuke"}', "sid", store, broadcaster
    )

    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_missing_type_field_is_dropped_silently():
    store = _InMemorySessionStore(_session(SessionStatus.PLAYING))
    broadcaster = _RecordingBroadcaster()

    await _handle_session_command(
        '{"foo":"bar"}', "sid", store, broadcaster
    )

    assert broadcaster.calls == []
