from datetime import datetime, timezone

import pytest

from app.domain.exceptions import InvalidPseudoError, PlayerAlreadyExistsError
from app.domain.player import Player
from app.usecase.create_or_get_player_usecase import CreateOrGetPlayerUseCase


class _InMemoryPlayerRepo:
    def __init__(self):
        self._by_pseudo: dict[str, Player] = {}
        self._next_id = 1

    async def create(self, pseudo: str) -> Player:
        if pseudo in self._by_pseudo:
            raise PlayerAlreadyExistsError(pseudo)
        player = Player(
            id=self._next_id,
            pseudo=pseudo,
            created_at=datetime.now(timezone.utc),
        )
        self._by_pseudo[pseudo] = player
        self._next_id += 1
        return player

    async def get_by_id(self, id_: int):
        for p in self._by_pseudo.values():
            if p.id == id_:
                return p
        return None

    async def get_by_pseudo(self, pseudo: str):
        return self._by_pseudo.get(pseudo)


@pytest.mark.asyncio
async def test_first_call_creates_player_with_default_hashtag():
    repo = _InMemoryPlayerRepo()
    player = await CreateOrGetPlayerUseCase(repo).execute("abc")
    assert player.pseudo == "ABC#HETIC"
    assert player.id == 1


@pytest.mark.asyncio
async def test_second_call_with_same_pseudo_returns_same_player():
    repo = _InMemoryPlayerRepo()
    usecase = CreateOrGetPlayerUseCase(repo)

    first = await usecase.execute("abc")
    second = await usecase.execute("ABC")  # different case, same canonical form
    third = await usecase.execute("abc#hetic")  # explicit default hashtag

    assert first.id == second.id == third.id
    assert first.created_at == second.created_at == third.created_at


@pytest.mark.asyncio
async def test_different_hashtags_create_distinct_players():
    repo = _InMemoryPlayerRepo()
    usecase = CreateOrGetPlayerUseCase(repo)

    a = await usecase.execute("abc#alpha")
    b = await usecase.execute("abc#beta1")

    assert a.id != b.id
    assert a.pseudo == "ABC#ALPHA"
    assert b.pseudo == "ABC#BETA1"


@pytest.mark.asyncio
async def test_invalid_pseudo_raises():
    repo = _InMemoryPlayerRepo()
    with pytest.raises(InvalidPseudoError):
        await CreateOrGetPlayerUseCase(repo).execute("AB")


@pytest.mark.asyncio
async def test_race_on_create_recovers_via_re_fetch():
    """Simulate a concurrent INSERT: get_by_pseudo says no, create raises duplicate."""

    class _RaceRepo(_InMemoryPlayerRepo):
        def __init__(self):
            super().__init__()
            self._race_done = False

        async def get_by_pseudo(self, pseudo: str):
            if not self._race_done:
                self._race_done = True
                return None  # first lookup: empty
            return self._by_pseudo.get(pseudo)

        async def create(self, pseudo: str):
            # Race winner already inserted the player.
            self._by_pseudo[pseudo] = Player(
                id=42, pseudo=pseudo, created_at=datetime.now(timezone.utc)
            )
            raise PlayerAlreadyExistsError(pseudo)

    repo = _RaceRepo()
    player = await CreateOrGetPlayerUseCase(repo).execute("abc")
    assert player.id == 42
    assert player.pseudo == "ABC#HETIC"
