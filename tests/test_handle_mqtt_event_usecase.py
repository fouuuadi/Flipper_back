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


def _session(session_id: str = "abc", score: int = 0, lives: int = 3, combo: int = 0) -> Session:
    return Session(
        session_id=session_id,
        pseudo="FOO#0001",
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

    await HandleMqttEventUseCase(store, broadcaster).execute(
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

    await HandleMqttEventUseCase(store, broadcaster).execute(
        MqttEvent(
            topic="flipper/bonus",
            payload={"type": "skill_shot", "points": 200, "sessionId": "abc"},
        )
    )

    persisted = await store.get("abc")
    assert persisted.score == 300
    assert persisted.combo == 5  # bonuses don't bump combo
    assert broadcaster.calls[-1][1]["score"] == 300
    assert broadcaster.calls[-1][1]["bonusType"] == "skill_shot"


@pytest.mark.asyncio
async def test_ball_lost_decrements_lives_and_resets_combo():
    session = _session(lives=3, combo=8)
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster).execute(
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

    await HandleMqttEventUseCase(store, _RecordingBroadcaster()).execute(
        MqttEvent(topic="flipper/ball/lost", payload={"sessionId": "abc"})
    )

    persisted = await store.get("abc")
    assert persisted.lives == 0


@pytest.mark.asyncio
async def test_game_over_sets_status_and_broadcasts_final_score():
    session = _session(score=4200)
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster).execute(
        MqttEvent(topic="flipper/game/over", payload={"sessionId": "abc"})
    )

    persisted = await store.get("abc")
    assert persisted.status == SessionStatus.OVER
    assert broadcaster.calls == [
        ("abc", {"type": "game:over", "finalScore": 4200})
    ]


@pytest.mark.asyncio
async def test_unknown_topic_is_ignored():
    session = _session(score=100)
    store = _InMemorySessionStore(session)
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster).execute(
        MqttEvent(topic="flipper/something/unknown", payload={"sessionId": "abc"})
    )

    persisted = await store.get("abc")
    assert persisted.score == 100  # untouched
    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_missing_session_id_is_dropped():
    store = _InMemorySessionStore(_session())
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster).execute(
        MqttEvent(topic="flipper/bumper/hit", payload={"points": 10})
    )

    assert broadcaster.calls == []


@pytest.mark.asyncio
async def test_unknown_session_is_dropped():
    store = _InMemorySessionStore()  # empty
    broadcaster = _RecordingBroadcaster()

    await HandleMqttEventUseCase(store, broadcaster).execute(
        MqttEvent(
            topic="flipper/bumper/hit",
            payload={"sessionId": "ghost", "points": 10},
        )
    )

    assert broadcaster.calls == []
