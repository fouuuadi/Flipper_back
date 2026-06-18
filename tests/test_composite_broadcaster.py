import pytest

from app.infrastructure.ws.composite_broadcaster import CompositeBroadcaster


class Recorder:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        self.calls.append((session_id, message))


@pytest.mark.asyncio
async def test_fans_out_to_all_broadcasters():
    a, b = Recorder(), Recorder()
    msg = {"type": "score:update", "score": 10}

    await CompositeBroadcaster(a, b).broadcast_to_session("s1", msg)

    assert a.calls == [("s1", msg)]
    assert b.calls == [("s1", msg)]


@pytest.mark.asyncio
async def test_empty_composite_is_noop():
    await CompositeBroadcaster().broadcast_to_session("s1", {"type": "x"})
