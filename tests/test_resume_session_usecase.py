import asyncio
from datetime import datetime, timezone

import pytest

from app.domain.ports.mqtt_gateway import MqttEvent
from app.domain.session import Session, SessionStatus
from app.usecase.handle_mqtt_event_usecase import HandleMqttEventUseCase
from app.usecase.resume_session_usecase import ResumeSessionUseCase
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


class _InMemoryEventBuffer:
    def __init__(self):
        self.buffers: dict[str, list[dict]] = {}

    async def push(self, session_id: str, event: dict) -> None:
        self.buffers.setdefault(session_id, []).append(event)

    async def read_all(self, session_id: str) -> list[dict]:
        return list(self.buffers.get(session_id, []))

    async def clear(self, session_id: str) -> None:
        self.buffers.pop(session_id, None)


async def _instant_sleep(_seconds: float) -> None:
    """Remplacement de sleep pour que les tests unitaires n'attendent pas 4 vraies secondes."""
    return None


def _session(status: SessionStatus = SessionStatus.PAUSED) -> Session:
    return Session(
        session_id="sid",
        pseudo="FOO",
        score=4200,
        lives=1,
        combo=5,
        status=status,
        room_code=None,
        created_at=datetime.now(timezone.utc),
    )


async def _drain_background_tasks() -> None:
    """Attend la fin des tâches fire-and-forget (le countdown).

    ResumeSessionUseCase lance le countdown via `asyncio.create_task` pour
    garder la boucle de réception WS réactive en prod ; dans les tests on
    draine ces tâches avant d'asserter sur la séquence de broadcast résultante.
    """
    pending = [
        t
        for t in asyncio.all_tasks()
        if t is not asyncio.current_task() and not t.done()
    ]
    if pending:
        await asyncio.gather(*pending)


@pytest.mark.asyncio
async def test_resume_orchestrates_ready_then_countdown_then_playing():
    store = _InMemorySessionStore(_session(SessionStatus.PAUSED))
    broadcaster = _RecordingBroadcaster()
    countdown = StartCountdownUseCase(store, broadcaster, sleep=_instant_sleep)

    await ResumeSessionUseCase(
        store, broadcaster, start_countdown=countdown.execute
    ).execute("sid")
    await _drain_background_tasks()

    # La séquence de broadcast exacte sur laquelle le front s'appuie.
    types_and_values = [
        (
            msg["type"],
            msg.get("status") if msg["type"] == "match:state" else msg.get("value"),
        )
        for _, msg in broadcaster.calls
    ]
    assert types_and_values == [
        ("match:state", "ready"),
        ("countdown:tick", 3),
        ("countdown:tick", 2),
        ("countdown:tick", 1),
        ("countdown:tick", 0),
        ("match:state", "playing"),
    ]
    # Total broadcasts = 1 (ready) + 4 (ticks) + 1 (playing).
    assert len(broadcaster.calls) == 2 + len(COUNTDOWN_VALUES)

    # État final : session PLAYING, score/lives/combo préservés.
    persisted = await store.get("sid")
    assert persisted.status == SessionStatus.PLAYING
    assert persisted.score == 4200
    assert persisted.lives == 1
    assert persisted.combo == 5


@pytest.mark.asyncio
async def test_resume_first_emits_match_state_ready_before_countdown_starts():
    """Sans le callback de countdown, le use case s'arrête après PAUSED → READY,
    prouvant que la transition READY se produit au début (et pas à la fin)."""
    store = _InMemorySessionStore(_session(SessionStatus.PAUSED))
    broadcaster = _RecordingBroadcaster()

    await ResumeSessionUseCase(store, broadcaster).execute("sid")

    persisted = await store.get("sid")
    assert persisted.status == SessionStatus.READY
    assert broadcaster.calls == [
        ("sid", {"type": "match:state", "status": "ready", "sessionId": "sid"})
    ]


@pytest.mark.asyncio
async def test_mqtt_score_event_dropped_while_session_is_in_resume_countdown():
    """Pendant la phase READY ouverte par cmd:resume, `HandleMqttEventUseCase`
    doit continuer à dropper les events score/ball — même gate que le countdown
    initial, pas de traitement spécial pour le resume."""
    store = _InMemorySessionStore(_session(SessionStatus.PAUSED))
    broadcaster = _RecordingBroadcaster()
    buffer = _InMemoryEventBuffer()

    # Lance le resume sans déclencher le countdown pour pouvoir sonder l'état
    # READY à loisir.
    await ResumeSessionUseCase(store, broadcaster).execute("sid")
    assert (await store.get("sid")).status == SessionStatus.READY

    # Un bumper hit arrive alors que le countdown serait encore en train de tourner.
    await HandleMqttEventUseCase(store, broadcaster, buffer).execute(
        MqttEvent(
            topic="flipper/bumper/hit",
            payload={"sessionId": "sid", "points": 50, "bumperId": 7},
        )
    )

    persisted = await store.get("sid")
    assert persisted.score == 4200  # inchangé
    assert await buffer.read_all("sid") == []
    # Le seul broadcast jusqu'ici est le match:state ready du resume.
    assert all(msg["type"] == "match:state" for _, msg in broadcaster.calls)


@pytest.mark.asyncio
async def test_resume_ignored_when_session_already_playing():
    store = _InMemorySessionStore(_session(SessionStatus.PLAYING))
    broadcaster = _RecordingBroadcaster()
    countdown = StartCountdownUseCase(store, broadcaster, sleep=_instant_sleep)

    await ResumeSessionUseCase(
        store, broadcaster, start_countdown=countdown.execute
    ).execute("sid")
    await _drain_background_tasks()

    assert (await store.get("sid")).status == SessionStatus.PLAYING
    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_resume_ignored_when_session_waiting():
    store = _InMemorySessionStore(_session(SessionStatus.WAITING))
    broadcaster = _RecordingBroadcaster()
    countdown = StartCountdownUseCase(store, broadcaster, sleep=_instant_sleep)

    await ResumeSessionUseCase(
        store, broadcaster, start_countdown=countdown.execute
    ).execute("sid")
    await _drain_background_tasks()

    assert (await store.get("sid")).status == SessionStatus.WAITING
    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_resume_ignored_when_session_over():
    store = _InMemorySessionStore(_session(SessionStatus.OVER))
    broadcaster = _RecordingBroadcaster()
    countdown = StartCountdownUseCase(store, broadcaster, sleep=_instant_sleep)

    await ResumeSessionUseCase(
        store, broadcaster, start_countdown=countdown.execute
    ).execute("sid")
    await _drain_background_tasks()

    assert (await store.get("sid")).status == SessionStatus.OVER
    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_resume_unknown_session_is_dropped():
    store = _InMemorySessionStore()
    broadcaster = _RecordingBroadcaster()
    countdown = StartCountdownUseCase(store, broadcaster, sleep=_instant_sleep)

    await ResumeSessionUseCase(
        store, broadcaster, start_countdown=countdown.execute
    ).execute("ghost")
    await _drain_background_tasks()

    assert broadcaster.calls == []
