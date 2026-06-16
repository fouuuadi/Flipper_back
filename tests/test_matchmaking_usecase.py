import asyncio
import pytest
from types import SimpleNamespace

from app.usecase.matchmaking_usecase import MatchmakingUseCase


class FakeMatchmakingRepo:
    def __init__(self):
        self.waiting = []
        self._id = 1
        self.lock = asyncio.Lock()

    async def claim_waiting_player(self, player_id: int, mode: str):
        async with self.lock:
            for m in self.waiting:
                if m['status'] == 'waiting' and m['mode'] == mode and m['player1_id'] != player_id:
                    m['player2_id'] = player_id
                    m['status'] = 'matched'
                    return SimpleNamespace(player1_id=m['player1_id'], id=m['id'])
            return None

    async def create(self, player_id: int, mode: str):
        async with self.lock:
            rec = {
                'id': self._id,
                'player1_id': player_id,
                'player2_id': None,
                'status': 'waiting',
                'mode': mode,
            }
            self._id += 1
            self.waiting.append(rec)
            return SimpleNamespace(**rec)

    async def update_matched(self, matchmaking_id: int, player2_id: int):
        async with self.lock:
            for m in self.waiting:
                if m['id'] == matchmaking_id:
                    m['player2_id'] = player2_id
                    m['status'] = 'matched'
                    return SimpleNamespace(**m)


class FakeRoomRepo:
    def __init__(self):
        self.created = []
        self._id = 1

    async def create(self, *args, **kwargs):
        r = SimpleNamespace(id=self._id, code=f"R{self._id}")
        self._id += 1
        self.created.append(r)
        return r


class FakeGameRepo:
    def __init__(self):
        self.created = []
        self._id = 1

    async def create(self, player_id: int, room_id: int):
        g = SimpleNamespace(id=self._id, player_id=player_id, room_id=room_id)
        self._id += 1
        self.created.append(g)
        return g


@pytest.mark.asyncio
async def test_matchmaking_no_opponent():
    mm = FakeMatchmakingRepo()
    room = FakeRoomRepo()
    game = FakeGameRepo()
    uc = MatchmakingUseCase(mm, room, game)

    res = await uc.execute(player_id=1, mode='1v1')

    assert res['status'] == 'waiting'
    assert 'matchmaking_id' in res
    assert len(mm.waiting) == 1


@pytest.mark.asyncio
async def test_matchmaking_found_opponent():
    mm = FakeMatchmakingRepo()
    room = FakeRoomRepo()
    game = FakeGameRepo()
    uc = MatchmakingUseCase(mm, room, game)

    res1 = await uc.execute(player_id=1, mode='1v1')
    assert res1['status'] == 'waiting'

    res2 = await uc.execute(player_id=2, mode='1v1')
    assert res2['status'] == 'matched'
    assert 'room_code' in res2
    assert len(res2['game_ids']) == 2
    assert len(room.created) == 1
    assert len(game.created) == 2


@pytest.mark.asyncio
async def test_matchmaking_race_condition():
    mm = FakeMatchmakingRepo()
    room = FakeRoomRepo()
    game = FakeGameRepo()
    uc = MatchmakingUseCase(mm, room, game)

    results = await asyncio.gather(
        uc.execute(player_id=1, mode='1v1'),
        uc.execute(player_id=2, mode='1v1'),
    )

    statuses = [r['status'] for r in results]
    assert 'matched' in statuses
    assert 'waiting' in statuses
    assert len(room.created) == 1
    assert len(game.created) == 2
