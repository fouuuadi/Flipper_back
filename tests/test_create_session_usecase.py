import re

import pytest

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
async def test_create_session_returns_session_with_formatted_pseudo():
    store = _InMemorySessionStore()
    usecase = CreateSessionUseCase(store)

    session = await usecase.execute("abc")

    assert re.fullmatch(r"ABC#\d{4}", session.pseudo)
    assert session.score == 0
    assert session.status == SessionStatus.WAITING
    assert session.room_code is None
    assert len(store.created) == 1
    assert store.created[0].session_id == session.session_id


@pytest.mark.asyncio
async def test_create_session_generates_unique_ids():
    store = _InMemorySessionStore()
    usecase = CreateSessionUseCase(store)

    s1 = await usecase.execute("abc")
    s2 = await usecase.execute("abc")

    assert s1.session_id != s2.session_id


@pytest.mark.asyncio
async def test_create_session_with_room_code():
    store = _InMemorySessionStore()
    usecase = CreateSessionUseCase(store)

    session = await usecase.execute("xyz", room_code="ROOM01")

    assert session.room_code == "ROOM01"
    assert session.pseudo.startswith("XYZ#")
