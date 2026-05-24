from datetime import datetime, timezone

import pytest

from app.domain.exceptions import PlayerNotFoundError
from app.domain.game import Game, GameMode, GameStatus
from app.domain.player import Player
from app.usecase.get_player_history_usecase import GetPlayerHistoryUseCase


class _InMemoryPlayerRepo:
    def __init__(self, *players: Player):
        self._by_id = {p.id: p for p in players}

    async def create(self, pseudo: str): ...  # pragma: no cover

    async def get_by_id(self, id_: int):
        return self._by_id.get(id_)

    async def get_by_pseudo(self, pseudo: str): ...  # pragma: no cover


class _InMemoryGameRepo:
    def __init__(self, games: list[Game], best_solo_score: int | None = None):
        self._games = games
        self._best_solo_score = best_solo_score
        self.last_call: dict | None = None

    async def get_finished_games_by_player(self, player_id, mode, limit):
        self.last_call = {"player_id": player_id, "mode": mode, "limit": limit}
        filtered = [g for g in self._games if g.player_id == player_id]
        if mode is not None:
            filtered = [g for g in filtered if g.mode == mode]
        return filtered[:limit]

    async def get_best_solo_score(self, player_id):
        return self._best_solo_score

    # unused interface bits (kept for ABC)
    async def create(self, *args, **kwargs): ...  # pragma: no cover
    async def leaderboard(self, *args, **kwargs): ...  # pragma: no cover
    async def persist_finished_session(self, *args, **kwargs): ...  # pragma: no cover
    async def get_by_id(self, *args, **kwargs): ...  # pragma: no cover
    async def add_points(self, *args, **kwargs): ...  # pragma: no cover
    async def get_active_by_room(self, *args, **kwargs): ...  # pragma: no cover
    async def finish(self, *args, **kwargs): ...  # pragma: no cover
    async def get_by_status(self, *args, **kwargs): ...  # pragma: no cover


def _game(player_id: int, mode: GameMode, score: int, id_: int = 0) -> Game:
    return Game(
        id=id_,
        player_id=player_id,
        room_id=None,
        mode=mode,
        score=score,
        status=GameStatus.FINISHED,
        started_at=datetime(2026, 5, 24, 10, 0, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 24, 10, 5, 0, tzinfo=timezone.utc),
    )


def _player(id_: int) -> Player:
    return Player(id=id_, pseudo="ABC#HETIC", created_at=datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_returns_player_and_games_for_known_id():
    player = _player(7)
    games = [
        _game(7, GameMode.SOLO, 100, id_=1),
        _game(7, GameMode.ONE_V_ONE, 200, id_=2),
    ]
    usecase = GetPlayerHistoryUseCase(
        _InMemoryPlayerRepo(player), _InMemoryGameRepo(games, best_solo_score=100)
    )

    returned_player, items = await usecase.execute(player_id=7, mode=None, limit=10)

    assert returned_player.id == 7
    assert [item.game.id for item in items] == [1, 2]


@pytest.mark.asyncio
async def test_unknown_player_raises_not_found():
    usecase = GetPlayerHistoryUseCase(_InMemoryPlayerRepo(), _InMemoryGameRepo([]))

    with pytest.raises(PlayerNotFoundError):
        await usecase.execute(player_id=42, mode=None, limit=10)


@pytest.mark.asyncio
async def test_player_with_no_games_returns_empty_list():
    usecase = GetPlayerHistoryUseCase(
        _InMemoryPlayerRepo(_player(1)), _InMemoryGameRepo([], best_solo_score=None)
    )

    _, items = await usecase.execute(player_id=1, mode=None, limit=10)
    assert items == []


@pytest.mark.asyncio
async def test_propagates_filters_to_game_repo():
    game_repo = _InMemoryGameRepo([])
    usecase = GetPlayerHistoryUseCase(_InMemoryPlayerRepo(_player(3)), game_repo)

    await usecase.execute(player_id=3, mode=GameMode.SOLO, limit=5)

    assert game_repo.last_call == {"player_id": 3, "mode": GameMode.SOLO, "limit": 5}


@pytest.mark.asyncio
async def test_flags_best_solo_game():
    player = _player(1)
    games = [
        _game(1, GameMode.SOLO, 1200, id_=1),
        _game(1, GameMode.SOLO, 4500, id_=2),  # best
        _game(1, GameMode.SOLO, 800, id_=3),
    ]
    usecase = GetPlayerHistoryUseCase(
        _InMemoryPlayerRepo(player), _InMemoryGameRepo(games, best_solo_score=4500)
    )

    _, items = await usecase.execute(player_id=1, mode=None, limit=10)

    by_id = {item.game.id: item.is_best for item in items}
    assert by_id == {1: False, 2: True, 3: False}


@pytest.mark.asyncio
async def test_1v1_games_never_flagged_as_best():
    player = _player(1)
    games = [
        _game(1, GameMode.ONE_V_ONE, 5000, id_=10),
        _game(1, GameMode.ONE_V_ONE, 3000, id_=11),
    ]
    # Even with a matching best_solo_score, 1v1 games must stay false.
    usecase = GetPlayerHistoryUseCase(
        _InMemoryPlayerRepo(player), _InMemoryGameRepo(games, best_solo_score=5000)
    )

    _, items = await usecase.execute(player_id=1, mode=None, limit=10)

    assert all(item.is_best is False for item in items)


@pytest.mark.asyncio
async def test_no_solo_record_means_no_flag():
    player = _player(1)
    games = [_game(1, GameMode.SOLO, 100, id_=1)]
    usecase = GetPlayerHistoryUseCase(
        _InMemoryPlayerRepo(player), _InMemoryGameRepo(games, best_solo_score=None)
    )

    _, items = await usecase.execute(player_id=1, mode=None, limit=10)

    assert items[0].is_best is False
