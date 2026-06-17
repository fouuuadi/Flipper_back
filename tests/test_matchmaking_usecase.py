import asyncio
import pytest
from types import SimpleNamespace

from app.domain.exceptions import PseudoCollisionInRoomError
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

    async def create(self, player_id: int, room_id: int, mode=None):
        g = SimpleNamespace(id=self._id, player_id=player_id, room_id=room_id)
        self._id += 1
        self.created.append(g)
        return g


class FakePlayerRepo:
    """Associe player_id → pseudo pour les tests."""
    def __init__(self, players: dict[int, str] | None = None):
        # players = {player_id: pseudo}
        self._players = players or {1: "AAA#11111", 2: "BBB#22222"}

    async def get_by_id(self, id: int):
        pseudo = self._players.get(id)
        if pseudo is None:
            return None
        return SimpleNamespace(id=id, pseudo=pseudo)

    async def get_by_pseudo(self, pseudo: str):
        for pid, p in self._players.items():
            if p == pseudo:
                return SimpleNamespace(id=pid, pseudo=p)
        return None

    async def create(self, pseudo: str):
        return SimpleNamespace(id=99, pseudo=pseudo)


class FakeSessionService:
    """Par défaut tous les pseudos sont uniques (aucune collision)."""
    def __init__(self, colliding_pseudos: set[str] | None = None):
        self._colliding = colliding_pseudos or set()

    async def check_pseudo_uniqueness_in_room(self, room_code: str, pseudo: str) -> bool:
        return pseudo not in self._colliding


def _make_uc(mm=None, room=None, game=None, players=None, session_svc=None):
    return MatchmakingUseCase(
        matchmaking_repo=mm or FakeMatchmakingRepo(),
        room_repo=room or FakeRoomRepo(),
        game_repo=game or FakeGameRepo(),
        player_repo=players or FakePlayerRepo(),
        session_service=session_svc or FakeSessionService(),
    )


@pytest.mark.asyncio
async def test_matchmaking_no_opponent():
    mm = FakeMatchmakingRepo()
    uc = _make_uc(mm=mm)

    res = await uc.execute(player_id=1, mode='1v1')

    assert res['status'] == 'waiting'
    assert 'matchmaking_id' in res
    assert len(mm.waiting) == 1


@pytest.mark.asyncio
async def test_matchmaking_found_opponent():
    mm = FakeMatchmakingRepo()
    room = FakeRoomRepo()
    game = FakeGameRepo()
    uc = _make_uc(mm=mm, room=room, game=game)

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
    uc = _make_uc(mm=mm, room=room, game=game)

    results = await asyncio.gather(
        uc.execute(player_id=1, mode='1v1'),
        uc.execute(player_id=2, mode='1v1'),
    )

    statuses = [r['status'] for r in results]
    assert 'matched' in statuses
    assert 'waiting' in statuses
    assert len(room.created) == 1
    assert len(game.created) == 2


@pytest.mark.asyncio
async def test_matchmaking_pseudo_collision():
    """Deux joueurs avec le même pseudo → PseudoCollisionInRoomError."""
    mm = FakeMatchmakingRepo()
    players = FakePlayerRepo({1: "AAA#11111", 2: "AAA#11111"})
    session_svc = FakeSessionService(colliding_pseudos={"AAA#11111"})
    uc = _make_uc(mm=mm, players=players, session_svc=session_svc)

    await uc.execute(player_id=1, mode='1v1')  

    with pytest.raises(PseudoCollisionInRoomError):
        await uc.execute(player_id=2, mode='1v1')


@pytest.mark.asyncio
async def test_matchmaking_pseudo_ok_different_pseudos():
    """Pseudos différents → pas de collision, match créé normalement."""
    mm = FakeMatchmakingRepo()
    room = FakeRoomRepo()
    game = FakeGameRepo()
    players = FakePlayerRepo({1: "AAA#11111", 2: "BBB#22222"})
    uc = _make_uc(mm=mm, room=room, game=game, players=players)

    await uc.execute(player_id=1, mode='1v1')
    res = await uc.execute(player_id=2, mode='1v1')

    assert res['status'] == 'matched'
    assert len(room.created) == 1
    assert len(game.created) == 2
