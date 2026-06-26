import pytest

from app.usecase.finish_borne_game_from_relay_usecase import (
    FinishBorneGameFromRelayUseCase,
)

BORNE_ID = "borne-1"


class FakeBorne:
    def __init__(self, active_session_id):
        self.active_session_id = active_session_id


class FakeBorneStore:
    def __init__(self, borne):
        self._borne = borne

    async def get_or_create(self, borne_id):
        return self._borne


class FakeSession:
    def __init__(self, score=0):
        self.score = score


class FakeSessionStore:
    def __init__(self, session):
        self._session = session
        self.updated: list[FakeSession] = []

    async def get(self, session_id):
        return self._session

    async def update(self, session):
        self.updated.append(session)


class FakeFinishBorneGame:
    def __init__(self):
        self.calls: list[str] = []

    async def execute(self, session_id):
        self.calls.append(session_id)


class FakeApplyIntent:
    def __init__(self):
        self.game_overs: list[str] = []

    async def mark_game_over(self, borne_id):
        self.game_overs.append(borne_id)


def _make(active_session_id, session):
    store = FakeSessionStore(session)
    finish = FakeFinishBorneGame()
    apply_intent = FakeApplyIntent()
    uc = FinishBorneGameFromRelayUseCase(
        borne_store=FakeBorneStore(FakeBorne(active_session_id)),
        session_store=store,
        finish_borne_game=finish,
        apply_intent=apply_intent,
    )
    return uc, store, finish, apply_intent


@pytest.mark.asyncio
async def test_writes_final_score_then_delegates_to_finish():
    session = FakeSession(score=0)
    uc, store, finish, apply_intent = _make("sess-1", session)

    await uc.execute(BORNE_ID, 4200)

    assert session.score == 4200
    assert store.updated == [session]
    assert finish.calls == ["sess-1"]
    assert apply_intent.game_overs == []  # délégué à FinishBorneGame


@pytest.mark.asyncio
async def test_non_int_score_finishes_without_overwriting():
    session = FakeSession(score=100)
    uc, store, finish, _ = _make("sess-1", session)

    await uc.execute(BORNE_ID, None)

    assert session.score == 100
    assert store.updated == []
    assert finish.calls == ["sess-1"]


@pytest.mark.asyncio
async def test_no_active_session_only_marks_game_over():
    uc, store, finish, apply_intent = _make(None, None)

    await uc.execute(BORNE_ID, 4200)

    assert apply_intent.game_overs == [BORNE_ID]
    assert finish.calls == []
    assert store.updated == []
