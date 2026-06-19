from datetime import datetime, timezone

import pytest

from app.domain.exceptions import InvalidPseudoError, PlayerNotFoundError
from app.domain.player import Player
from app.usecase.get_player_usecase import GetPlayerUseCase


class _InMemoryPlayerRepo:
    def __init__(self, *players: Player):
        self._players = {p.id: p for p in players}

    async def create(self, pseudo: str) -> Player:  # pragma: no cover - not used here
        raise NotImplementedError

    async def get_by_id(self, id_: int):
        return self._players.get(id_)

    async def get_by_pseudo(self, pseudo: str):
        for p in self._players.values():
            if p.pseudo == pseudo:
                return p
        return None


def _player(id_: int, pseudo: str) -> Player:
    return Player(id=id_, pseudo=pseudo, created_at=datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_get_by_id_returns_player():
    repo = _InMemoryPlayerRepo(_player(1, "ABC"))
    player = await GetPlayerUseCase(repo).execute_by_id(1)
    assert player.id == 1


@pytest.mark.asyncio
async def test_get_by_id_missing_raises():
    repo = _InMemoryPlayerRepo()
    with pytest.raises(PlayerNotFoundError):
        await GetPlayerUseCase(repo).execute_by_id(999)


@pytest.mark.asyncio
async def test_get_by_pseudo_normalises_input():
    repo = _InMemoryPlayerRepo(_player(1, "ABC"))
    # Raw "abc" should resolve to ABC via the helper.
    player = await GetPlayerUseCase(repo).execute_by_pseudo("abc")
    assert player.pseudo == "ABC"


@pytest.mark.asyncio
async def test_get_by_pseudo_missing_raises():
    repo = _InMemoryPlayerRepo(_player(1, "ABC"))
    with pytest.raises(PlayerNotFoundError):
        await GetPlayerUseCase(repo).execute_by_pseudo("xyz")


@pytest.mark.asyncio
async def test_get_by_pseudo_invalid_format_raises_validation_error():
    repo = _InMemoryPlayerRepo()
    with pytest.raises(InvalidPseudoError):
        await GetPlayerUseCase(repo).execute_by_pseudo("AB")
