from unittest.mock import AsyncMock

import pytest

from app.infrastructure.ws.borne_hub import BorneHub, BorneHubManager


@pytest.mark.asyncio
async def test_get_or_create_returns_same_instance():
    mgr = BorneHubManager()
    hub1 = mgr.get_or_create("borne-1")
    hub2 = mgr.get_or_create("borne-1")
    assert hub1 is hub2


@pytest.mark.asyncio
async def test_add_and_remove_client():
    hub = BorneHub("borne-x")
    ws = AsyncMock()
    await hub.add_client(ws)
    assert ws in hub.clients
    await hub.remove_client(ws)
    assert ws not in hub.clients


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_clients():
    hub = BorneHub("borne-x")
    ws1, ws2 = AsyncMock(), AsyncMock()
    await hub.add_client(ws1)
    await hub.add_client(ws2)

    msg = {"type": "nav:state", "nav": "menu", "sessionId": None}
    await hub.broadcast(msg)

    ws1.send_json.assert_awaited_once_with(msg)
    ws2.send_json.assert_awaited_once_with(msg)


@pytest.mark.asyncio
async def test_broadcast_to_borne_routes_to_hub():
    mgr = BorneHubManager()
    hub = mgr.get_or_create("borne-x")
    ws = AsyncMock()
    await hub.add_client(ws)

    await mgr.broadcast_to_borne("borne-x", {"type": "ping"})

    ws.send_json.assert_awaited_once_with({"type": "ping"})


@pytest.mark.asyncio
async def test_broadcast_to_unknown_borne_is_noop():
    mgr = BorneHubManager()
    await mgr.broadcast_to_borne("ghost", {"type": "noop"})


@pytest.mark.asyncio
async def test_broadcast_to_session_shim_reaches_borne_clients():
    """Le shim ignore le session_id et diffuse à tous les écrans de la borne :
    c'est ce qui permet aux use cases de match d'émettre sur le bus borne."""
    mgr = BorneHubManager()
    hub = mgr.get_or_create("borne-x")
    ws = AsyncMock()
    await hub.add_client(ws)

    await mgr.broadcast_to_session("any-session-id", {"type": "match:state"})

    ws.send_json.assert_awaited_once_with({"type": "match:state"})


@pytest.mark.asyncio
async def test_broadcast_swallows_send_failures():
    hub = BorneHub("borne-x")
    bad_ws = AsyncMock()
    bad_ws.send_json.side_effect = RuntimeError("connection closed")
    good_ws = AsyncMock()
    await hub.add_client(bad_ws)
    await hub.add_client(good_ws)

    await hub.broadcast({"type": "ping"})

    good_ws.send_json.assert_awaited_once()
