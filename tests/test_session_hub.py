from unittest.mock import AsyncMock

import pytest

from app.infrastructure.ws.session_hub import SessionHub, SessionHubManager


@pytest.mark.asyncio
async def test_get_or_create_returns_same_instance():
    mgr = SessionHubManager()
    hub1 = mgr.get_or_create("sess-1")
    hub2 = mgr.get_or_create("sess-1")
    assert hub1 is hub2


@pytest.mark.asyncio
async def test_isolated_session_hubs():
    mgr = SessionHubManager()
    hub_a = mgr.get_or_create("sess-a")
    hub_b = mgr.get_or_create("sess-b")
    assert hub_a is not hub_b


@pytest.mark.asyncio
async def test_add_and_remove_client():
    hub = SessionHub("sess-x")
    ws = AsyncMock()
    await hub.add_client(ws)
    assert ws in hub.clients
    await hub.remove_client(ws)
    assert ws not in hub.clients


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_clients():
    hub = SessionHub("sess-x")
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await hub.add_client(ws1)
    await hub.add_client(ws2)

    msg = {"type": "score:update", "score": 100}
    await hub.broadcast(msg)

    ws1.send_json.assert_awaited_once_with(msg)
    ws2.send_json.assert_awaited_once_with(msg)


@pytest.mark.asyncio
async def test_broadcast_to_unknown_session_is_noop():
    mgr = SessionHubManager()
    # ne doit pas lever même si aucun hub n'existe pour cette session
    await mgr.broadcast_to_session("ghost", {"type": "noop"})


@pytest.mark.asyncio
async def test_broadcast_to_session_routes_to_hub():
    mgr = SessionHubManager()
    hub = mgr.get_or_create("sess-x")
    ws = AsyncMock()
    await hub.add_client(ws)

    await mgr.broadcast_to_session("sess-x", {"type": "ping"})

    ws.send_json.assert_awaited_once_with({"type": "ping"})


@pytest.mark.asyncio
async def test_broadcast_swallows_send_failures():
    """Un WS mort ne doit pas bloquer le reste du broadcast."""
    hub = SessionHub("sess-x")
    bad_ws = AsyncMock()
    bad_ws.send_json.side_effect = RuntimeError("connection closed")
    good_ws = AsyncMock()
    await hub.add_client(bad_ws)
    await hub.add_client(good_ws)

    await hub.broadcast({"type": "ping"})

    good_ws.send_json.assert_awaited_once()
