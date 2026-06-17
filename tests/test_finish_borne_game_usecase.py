import pytest

from app.domain.borne import Borne, BorneNavState
from app.domain.exceptions import SessionNotFoundError
from app.domain.ports.borne_store import BorneStore
from app.usecase.apply_borne_intent_usecase import ApplyBorneIntentUseCase
from app.usecase.finish_borne_game_usecase import FinishBorneGameUseCase

BORNE_ID = "borne-test"
SESSION_ID = "sess-1"


class FakeBorneStore(BorneStore):
    def __init__(self, initial: Borne):
        self._bornes = {initial.borne_id: initial}

    async def get_or_create(self, borne_id: str) -> Borne:
        if borne_id not in self._bornes:
            self._bornes[borne_id] = Borne(borne_id=borne_id)
        return self._bornes[borne_id]

    async def update(self, borne: Borne) -> None:
        self._bornes[borne.borne_id] = borne


class RecordingBroadcaster:
    def __init__(self):
        self.messages: list[dict] = []

    async def broadcast_to_borne(self, borne_id: str, message: dict) -> None:
        self.messages.append(message)

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        self.messages.append(message)


class FakeFinishAndPersist:
    def __init__(self, raises: bool = False):
        self.calls: list[str] = []
        self._raises = raises

    async def execute(self, session_id: str) -> None:
        self.calls.append(session_id)
        if self._raises:
            raise SessionNotFoundError(session_id)


def _build(borne: Borne, persist: FakeFinishAndPersist):
    store = FakeBorneStore(borne)
    bus = RecordingBroadcaster()
    apply_intent = ApplyBorneIntentUseCase(store, bus, session_store=None)
    uc = FinishBorneGameUseCase(store, BORNE_ID, apply_intent, persist)
    return uc, store, bus


@pytest.mark.asyncio
async def test_persists_and_marks_game_over_for_borne_session():
    persist = FakeFinishAndPersist()
    borne = Borne(
        borne_id=BORNE_ID, nav=BorneNavState.IN_GAME, active_session_id=SESSION_ID
    )
    uc, store, bus = _build(borne, persist)

    await uc.execute(SESSION_ID)

    assert (await store.get_or_create(BORNE_ID)).nav == BorneNavState.GAME_OVER
    assert persist.calls == [SESSION_ID]
    assert bus.messages[-1]["nav"] == "game_over"


@pytest.mark.asyncio
async def test_noop_for_session_not_attached_to_borne():
    persist = FakeFinishAndPersist()
    borne = Borne(
        borne_id=BORNE_ID, nav=BorneNavState.IN_GAME, active_session_id=SESSION_ID
    )
    uc, store, bus = _build(borne, persist)

    await uc.execute("some-legacy-session")

    # Borne untouched, no persistence: POST /scores handles legacy sessions.
    assert (await store.get_or_create(BORNE_ID)).nav == BorneNavState.IN_GAME
    assert persist.calls == []
    assert bus.messages == []


@pytest.mark.asyncio
async def test_swallows_session_not_found():
    persist = FakeFinishAndPersist(raises=True)
    borne = Borne(
        borne_id=BORNE_ID, nav=BorneNavState.IN_GAME, active_session_id=SESSION_ID
    )
    uc, store, _ = _build(borne, persist)

    # Must not raise even if the session vanished before persistence.
    await uc.execute(SESSION_ID)

    assert (await store.get_or_create(BORNE_ID)).nav == BorneNavState.GAME_OVER
    assert persist.calls == [SESSION_ID]
