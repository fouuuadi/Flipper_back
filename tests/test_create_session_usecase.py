import pytest

from app.domain.exceptions import InvalidPseudoError
from app.domain.session import Session, SessionStatus
from app.usecase.create_session_usecase import CreateSessionUseCase


class _InMemorySessionStore:
    def __init__(self):
        self.created: list[Session] = []

    async def create(self, session: Session) -> None:
        self.created.append(session)

    async def get(self, session_id: str):
        for s in self.created:
            if s.session_id == session_id:
                return s
        return None

    async def update(self, session: Session) -> None:
        for i, s in enumerate(self.created):
            if s.session_id == session.session_id:
                self.created[i] = session
                return

    async def delete(self, session_id: str) -> None:
        self.created = [s for s in self.created if s.session_id != session_id]


@pytest.mark.asyncio
async def test_create_session_applies_default_hashtag_when_missing():
    store = _InMemorySessionStore()
    usecase = CreateSessionUseCase(store)

    session = await usecase.execute("abc")

    assert session.pseudo == "ABC"
    assert session.score == 0
    assert session.status == SessionStatus.WAITING
    assert session.room_code is None
    assert len(store.created) == 1
    assert store.created[0].session_id == session.session_id


@pytest.mark.asyncio
async def test_create_session_keeps_user_provided_hashtag():
    store = _InMemorySessionStore()
    usecase = CreateSessionUseCase(store)

    session = await usecase.execute("foo")

    assert session.pseudo == "FOO"


@pytest.mark.asyncio
async def test_create_session_generates_unique_ids():
    store = _InMemorySessionStore()
    usecase = CreateSessionUseCase(store)

    s1 = await usecase.execute("abc")
    s2 = await usecase.execute("abc")

    # Même pseudo (plus de suffixe aléatoire) mais des session ids distincts.
    assert s1.pseudo == s2.pseudo == "ABC"
    assert s1.session_id != s2.session_id


@pytest.mark.asyncio
async def test_create_session_with_room_code():
    store = _InMemorySessionStore()
    usecase = CreateSessionUseCase(store)

    session = await usecase.execute("xyz", room_code="ROOM01")

    assert session.room_code == "ROOM01"
    assert session.pseudo == "XYZ"


@pytest.mark.asyncio
async def test_create_session_rejects_invalid_pseudo():
    store = _InMemorySessionStore()
    usecase = CreateSessionUseCase(store)

    with pytest.raises(InvalidPseudoError):
        await usecase.execute("AB")  # trop court

    with pytest.raises(InvalidPseudoError):
        await usecase.execute("ab@")  # caractère invalide

    with pytest.raises(InvalidPseudoError):
        await usecase.execute("ABCD")  # trop long
