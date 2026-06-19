from datetime import datetime, timezone

import pytest

from app.domain.borne import Borne, BorneNavState
from app.domain.ports.borne_store import BorneStore
from app.domain.ports.session_store import SessionStore
from app.domain.session import Session, SessionStatus
from app.usecase.apply_borne_intent_usecase import (
    ApplyBorneIntentUseCase,
    next_nav_state,
)

BORNE_ID = "borne-test"


class FakeBorneStore(BorneStore):
    def __init__(self, initial: Borne | None = None):
        self._bornes: dict[str, Borne] = {}
        if initial is not None:
            self._bornes[initial.borne_id] = initial

    async def get_or_create(self, borne_id: str) -> Borne:
        if borne_id not in self._bornes:
            self._bornes[borne_id] = Borne(borne_id=borne_id)
        return self._bornes[borne_id]

    async def update(self, borne: Borne) -> None:
        self._bornes[borne.borne_id] = borne


class FakeSessionStore(SessionStore):
    def __init__(self):
        self.sessions: dict[str, Session] = {}

    async def create(self, session: Session) -> None:
        self.sessions[session.session_id] = session

    async def get(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    async def update(self, session: Session) -> None:
        self.sessions[session.session_id] = session

    async def delete(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)


class RecordingBroadcaster:
    def __init__(self):
        self.messages: list[dict] = []

    async def broadcast_to_borne(self, borne_id: str, message: dict) -> None:
        self.messages.append(message)

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        self.messages.append(message)

    def of_type(self, msg_type: str) -> list[dict]:
        return [m for m in self.messages if m.get("type") == msg_type]


@pytest.fixture
def no_background_countdown(monkeypatch):
    """Empêche ReadyUp de lancer le countdown en tâche de fond (testé ailleurs)."""

    def _swallow(coro):
        coro.close()
        return None

    monkeypatch.setattr(
        "app.usecase.ready_up_usecase.asyncio.create_task", _swallow
    )


def _usecase(borne: Borne | None = None, sessions: FakeSessionStore | None = None):
    store = FakeBorneStore(borne)
    bus = RecordingBroadcaster()
    uc = ApplyBorneIntentUseCase(store, bus, sessions or FakeSessionStore())
    return uc, store, bus


def _playing_session(session_id: str = "sess-1") -> Session:
    return Session(
        session_id=session_id,
        pseudo="ABC",
        status=SessionStatus.PLAYING,
        created_at=datetime.now(timezone.utc),
    )


# --- navigation ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_press_a_moves_splash_to_menu_and_broadcasts():
    uc, store, bus = _usecase()

    await uc.execute(BORNE_ID, "PRESS_A")

    assert (await store.get_or_create(BORNE_ID)).nav == BorneNavState.MENU
    assert bus.messages == [
        {"type": "nav:state", "nav": "menu", "sessionId": None}
    ]


@pytest.mark.asyncio
async def test_menu_open_boutique_then_back():
    uc, store, _ = _usecase(Borne(borne_id=BORNE_ID, nav=BorneNavState.MENU))

    await uc.execute(BORNE_ID, "OPEN_BOUTIQUE")
    assert (await store.get_or_create(BORNE_ID)).nav == BorneNavState.BOUTIQUE

    await uc.execute(BORNE_ID, "BACK_TO_MENU")
    assert (await store.get_or_create(BORNE_ID)).nav == BorneNavState.MENU


@pytest.mark.asyncio
async def test_invalid_action_is_noop_and_silent():
    uc, store, bus = _usecase()  # nav=splash

    await uc.execute(BORNE_ID, "START_GAME")  # invalide depuis splash

    assert (await store.get_or_create(BORNE_ID)).nav == BorneNavState.SPLASH
    assert bus.messages == []


@pytest.mark.asyncio
async def test_replay_from_game_over_clears_active_session():
    initial = Borne(
        borne_id=BORNE_ID, nav=BorneNavState.GAME_OVER, active_session_id="sess-123"
    )
    uc, store, bus = _usecase(initial)

    await uc.execute(BORNE_ID, "REPLAY")

    borne = await store.get_or_create(BORNE_ID)
    assert borne.nav == BorneNavState.IDENTIFICATION
    assert borne.active_session_id is None
    assert bus.messages[-1]["sessionId"] is None


# --- démarrage de partie (#129) ----------------------------------------------


@pytest.mark.asyncio
async def test_players_validated_creates_session_and_starts_match(
    no_background_countdown,
):
    sessions = FakeSessionStore()
    uc, store, bus = _usecase(
        Borne(borne_id=BORNE_ID, nav=BorneNavState.IDENTIFICATION), sessions
    )

    await uc.execute(BORNE_ID, "PLAYERS_VALIDATED", {"pseudo": "ABC", "mode": "solo"})

    borne = await store.get_or_create(BORNE_ID)
    assert borne.nav == BorneNavState.IN_GAME
    assert borne.active_session_id is not None

    # Session bien créée et rattachée à la borne.
    assert len(sessions.sessions) == 1
    created = next(iter(sessions.sessions.values()))
    assert created.session_id == borne.active_session_id

    # nav:state in_game broadcasté avec le sessionId.
    nav = bus.of_type("nav:state")[-1]
    assert nav["nav"] == "in_game"
    assert nav["sessionId"] == borne.active_session_id

    # ReadyUp a broadcasté match:state ready sur le bus borne.
    ready = [m for m in bus.of_type("match:state") if m.get("status") == "ready"]
    assert ready


@pytest.mark.asyncio
async def test_players_validated_ignored_outside_identification(
    no_background_countdown,
):
    sessions = FakeSessionStore()
    uc, store, bus = _usecase(
        Borne(borne_id=BORNE_ID, nav=BorneNavState.MENU), sessions
    )

    await uc.execute(BORNE_ID, "PLAYERS_VALIDATED", {"pseudo": "ABC"})

    assert (await store.get_or_create(BORNE_ID)).nav == BorneNavState.MENU
    assert sessions.sessions == {}
    assert bus.messages == []


@pytest.mark.asyncio
async def test_players_validated_without_pseudo_is_dropped(no_background_countdown):
    sessions = FakeSessionStore()
    uc, store, _ = _usecase(
        Borne(borne_id=BORNE_ID, nav=BorneNavState.IDENTIFICATION), sessions
    )

    await uc.execute(BORNE_ID, "PLAYERS_VALIDATED", {"mode": "solo"})

    assert (await store.get_or_create(BORNE_ID)).nav == BorneNavState.IDENTIFICATION
    assert sessions.sessions == {}


# --- contrôles de match (#129) ------------------------------------------------


@pytest.mark.asyncio
async def test_pause_command_routes_to_active_session():
    sessions = FakeSessionStore()
    await sessions.create(_playing_session("sess-1"))
    uc, _, bus = _usecase(
        Borne(borne_id=BORNE_ID, nav=BorneNavState.IN_GAME, active_session_id="sess-1"),
        sessions,
    )

    await uc.handle_match_command(BORNE_ID, "cmd:pause")

    assert (await sessions.get("sess-1")).status == SessionStatus.PAUSED
    paused = [m for m in bus.of_type("match:state") if m.get("status") == "paused"]
    assert paused


@pytest.mark.asyncio
async def test_abandon_command_marks_borne_game_over():
    sessions = FakeSessionStore()
    await sessions.create(_playing_session("sess-1"))
    uc, store, bus = _usecase(
        Borne(borne_id=BORNE_ID, nav=BorneNavState.IN_GAME, active_session_id="sess-1"),
        sessions,
    )

    await uc.handle_match_command(BORNE_ID, "cmd:abandon")

    assert (await sessions.get("sess-1")).status == SessionStatus.OVER
    borne = await store.get_or_create(BORNE_ID)
    assert borne.nav == BorneNavState.GAME_OVER
    assert bus.of_type("nav:state")[-1]["nav"] == "game_over"


@pytest.mark.asyncio
async def test_command_without_active_session_is_noop():
    uc, _, bus = _usecase(Borne(borne_id=BORNE_ID, nav=BorneNavState.MENU))

    await uc.handle_match_command(BORNE_ID, "cmd:pause")

    assert bus.messages == []


# --- table pure ---------------------------------------------------------------


@pytest.mark.parametrize(
    "current,action,expected",
    [
        (BorneNavState.SPLASH, "PRESS_A", BorneNavState.MENU),
        (BorneNavState.MENU, "START_GAME", BorneNavState.IDENTIFICATION),
        (BorneNavState.MENU, "OPEN_LEADERBOARD", BorneNavState.LEADERBOARD),
        (BorneNavState.MENU, "OPEN_SETTINGS", BorneNavState.SETTINGS),
        (BorneNavState.IDENTIFICATION, "BACK_TO_MENU", BorneNavState.MENU),
        (BorneNavState.SPLASH, "BACK_TO_MENU", None),
        (BorneNavState.MENU, "NOPE", None),
    ],
)
def test_next_nav_state_table(current, action, expected):
    assert next_nav_state(current, action) == expected
