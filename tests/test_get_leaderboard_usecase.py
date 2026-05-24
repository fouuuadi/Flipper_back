import pytest

from app.domain.game import GameMode
from app.domain.leaderboard_entry import LeaderboardEntry
from app.usecase.get_leaderboard_usecase import GetLeaderboardUseCase


class _RecordingRepo:
    def __init__(self, response: list[LeaderboardEntry]):
        self._response = response
        self.last_call: dict | None = None

    async def leaderboard(self, mode, limit):
        self.last_call = {"mode": mode, "limit": limit}
        return self._response


@pytest.mark.asyncio
async def test_passes_arguments_to_repository():
    repo = _RecordingRepo([])
    await GetLeaderboardUseCase(repo).execute(mode=GameMode.SOLO, limit=25)
    assert repo.last_call == {"mode": GameMode.SOLO, "limit": 25}


@pytest.mark.asyncio
async def test_returns_repository_payload_verbatim():
    payload = [
        LeaderboardEntry(rank=1, player_id=10, pseudo="ABC#HETIC", score=4000),
        LeaderboardEntry(rank=2, player_id=11, pseudo="XYZ#ALPHA", score=2000),
    ]
    repo = _RecordingRepo(payload)

    result = await GetLeaderboardUseCase(repo).execute(mode=None, limit=10)

    assert result == payload


@pytest.mark.asyncio
async def test_empty_payload_propagates():
    repo = _RecordingRepo([])
    result = await GetLeaderboardUseCase(repo).execute(mode=GameMode.ONE_V_ONE, limit=10)
    assert result == []
