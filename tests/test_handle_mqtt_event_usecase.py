from datetime import datetime, timezone

import pytest

from app.domain.ports.mqtt_gateway import MqttEvent
from app.domain.session import Session, SessionStatus
from app.usecase.handle_mqtt_event_usecase import HandleMqttEventUseCase


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


def _session(session_id: str = "abc", score: int = 0, lives: int = 3, combo: int = 0) -> Session:
    return Session(
        session_id=session_id,
        pseudo="FOO",
        score=score,
        lives=lives,
        combo=combo,
        status=SessionStatus.PLAYING,
        room_code=None,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_bumper_hit_updates_score_combo_and_broadcasts():
    session = _session(score=100, combo=2)
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster, _InMemoryEventBuffer()).execute(
        MqttEvent(
            topic="flipper/bumper/hit",
            payload={"bumperId": 7, "points": 50, "sessionId": "abc"},
        )
    )

    persisted = await store.get("abc")
    assert persisted.score == 150
    assert persisted.combo == 3
    assert broadcaster.calls == [
        (
            "abc",
            {"type": "score:update", "score": 150, "combo": 3, "bumperId": 7},
        )
    ]


@pytest.mark.asyncio
async def test_bonus_adds_points_without_touching_combo():
    session = _session(score=100, combo=5)
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster, _InMemoryEventBuffer()).execute(
        MqttEvent(
            topic="flipper/bonus",
            payload={"type": "skill_shot", "points": 200, "sessionId": "abc"},
        )
    )

    persisted = await store.get("abc")
    assert persisted.score == 300
    assert persisted.combo == 5  # les bonus n'incrémentent pas le combo
    assert broadcaster.calls[-1][1]["score"] == 300
    assert broadcaster.calls[-1][1]["bonusType"] == "skill_shot"


@pytest.mark.asyncio
async def test_ball_lost_decrements_lives_and_resets_combo():
    session = _session(lives=3, combo=8)
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster, _InMemoryEventBuffer()).execute(
        MqttEvent(topic="flipper/ball/lost", payload={"sessionId": "abc"})
    )

    persisted = await store.get("abc")
    assert persisted.lives == 2
    assert persisted.combo == 0
    assert broadcaster.calls == [
        ("abc", {"type": "ball:lost", "livesRemaining": 2})
    ]


@pytest.mark.asyncio
async def test_ball_lost_floors_at_zero():
    session = _session(lives=0)
    store = _InMemorySessionStore(session)

    await HandleMqttEventUseCase(store, _RecordingBroadcaster(), _InMemoryEventBuffer()).execute(
        MqttEvent(topic="flipper/ball/lost", payload={"sessionId": "abc"})
    )

    persisted = await store.get("abc")
    assert persisted.lives == 0


@pytest.mark.asyncio
async def test_game_over_sets_status_and_broadcasts_final_score_and_match_state():
    session = _session(score=4200)
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster, _InMemoryEventBuffer()).execute(
        MqttEvent(topic="flipper/game/over", payload={"sessionId": "abc"})
    )

    persisted = await store.get("abc")
    assert persisted.status == SessionStatus.OVER
    # Deux messages : notification du score final + transition de cycle de vie.
    assert broadcaster.calls == [
        ("abc", {"type": "game:over", "finalScore": 4200}),
        ("abc", {"type": "match:state", "status": "over", "sessionId": "abc"}),
    ]


@pytest.mark.asyncio
async def test_game_over_fires_on_game_over_callback():
    store = _InMemorySessionStore(_session(score=4200))
    fired: list[str] = []

    async def on_game_over(session_id: str) -> None:
        fired.append(session_id)

    await HandleMqttEventUseCase(
        store, _RecordingBroadcaster(), _InMemoryEventBuffer(), on_game_over=on_game_over
    ).execute(MqttEvent(topic="flipper/game/over", payload={"sessionId": "abc"}))

    assert fired == ["abc"]


@pytest.mark.asyncio
async def test_non_game_over_does_not_fire_callback():
    store = _InMemorySessionStore(_session())
    fired: list[str] = []

    async def on_game_over(session_id: str) -> None:
        fired.append(session_id)

    await HandleMqttEventUseCase(
        store, _RecordingBroadcaster(), _InMemoryEventBuffer(), on_game_over=on_game_over
    ).execute(
        MqttEvent(topic="flipper/bumper/hit", payload={"sessionId": "abc", "points": 10})
    )

    assert fired == []


@pytest.mark.asyncio
async def test_score_event_dropped_when_session_not_playing():
    session = _session(score=100)
    session.status = SessionStatus.PAUSED
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()
    buffer = _InMemoryEventBuffer()

    await HandleMqttEventUseCase(store, broadcaster, buffer).execute(
        MqttEvent(
            topic="flipper/bumper/hit",
            payload={"sessionId": "abc", "points": 50, "bumperId": 1},
        )
    )

    persisted = await store.get("abc")
    assert persisted.score == 100  # inchangé
    assert broadcaster.calls == []
    assert await buffer.read_all("abc") == []


@pytest.mark.asyncio
async def test_score_event_dropped_when_session_in_ready_countdown():
    session = _session(score=0)
    session.status = SessionStatus.READY
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster, _InMemoryEventBuffer()).execute(
        MqttEvent(
            topic="flipper/bumper/hit",
            payload={"sessionId": "abc", "points": 50},
        )
    )

    persisted = await store.get("abc")
    assert persisted.score == 0
    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_unknown_topic_is_ignored():
    session = _session(score=100)
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster, _InMemoryEventBuffer()).execute(
        MqttEvent(topic="flipper/something/unknown", payload={"sessionId": "abc"})
    )

    persisted = await store.get("abc")
    assert persisted.score == 100  # intact
    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_missing_session_id_is_dropped():
    store = _InMemorySessionStore(_session())
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster, _InMemoryEventBuffer()).execute(
        MqttEvent(topic="flipper/bumper/hit", payload={"points": 10})
    )

    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_unknown_session_is_dropped():
    store = _InMemorySessionStore()  # vide
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster, _InMemoryEventBuffer()).execute(
        MqttEvent(
            topic="flipper/bumper/hit",
            payload={"sessionId": "ghost", "points": 10},
        )
    )

    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_handled_events_are_pushed_to_buffer():
    session = _session()
    store = _InMemorySessionStore(session)
    buffer = _InMemoryEventBuffer()

    usecase = HandleMqttEventUseCase(store, _RecordingBroadcaster(), buffer)
    await usecase.execute(
        MqttEvent(
            topic="flipper/bumper/hit",
            payload={"sessionId": "abc", "points": 100, "bumperId": 3},
        )
    )
    await usecase.execute(
        MqttEvent(topic="flipper/ball/lost", payload={"sessionId": "abc"})
    )

    buffered = await buffer.read_all("abc")
    assert len(buffered) == 2
    assert buffered[0]["topic"] == "flipper/bumper/hit"
    assert buffered[0]["payload"]["bumperId"] == 3
    assert "occured_at" in buffered[0]
    assert buffered[1]["topic"] == "flipper/ball/lost"


@pytest.mark.asyncio
async def test_dropped_events_are_not_pushed_to_buffer():
    store = _InMemorySessionStore(_session())
    buffer = _InMemoryEventBuffer()

    # sessionId manquant → drop
    await HandleMqttEventUseCase(store, _RecordingBroadcaster(), buffer).execute(
        MqttEvent(topic="flipper/bumper/hit", payload={"points": 10})
    )
    # topic inconnu → drop
    await HandleMqttEventUseCase(store, _RecordingBroadcaster(), buffer).execute(
        MqttEvent(topic="flipper/garbage", payload={"sessionId": "abc"})
    )

    assert await buffer.read_all("abc") == []
