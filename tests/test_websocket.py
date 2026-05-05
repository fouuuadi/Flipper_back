import pytest
from unittest.mock import AsyncMock
from app.infrastructure.ws.room_hub import RoomHub, HubManager


@pytest.mark.asyncio
async def test_hub_manager_get_or_create_room_hub():
    """UC-06 : Test création hub pour room."""
    hub_manager = HubManager()
    
    hub1 = hub_manager.get_or_create_room_hub("TEST123")
    assert hub1 is not None
    assert hub1.room_code == "TEST123"
    assert len(hub1.clients) == 0
    
    # Vérifier que c'est le même hub
    hub2 = hub_manager.get_or_create_room_hub("TEST123")
    assert hub1 is hub2


@pytest.mark.asyncio
async def test_room_hub_add_client():
    """UC-06 : Test ajout client au hub."""
    hub = RoomHub("TEST123")
    
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    
    await hub.add_client(mock_ws1)
    assert len(hub.clients) == 1
    assert mock_ws1 in hub.clients
    
    await hub.add_client(mock_ws2)
    assert len(hub.clients) == 2
    assert mock_ws2 in hub.clients


@pytest.mark.asyncio
async def test_room_hub_remove_client():
    """UC-06 : Test retrait client du hub."""
    hub = RoomHub("TEST123")
    
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    
    await hub.add_client(mock_ws1)
    await hub.add_client(mock_ws2)
    assert len(hub.clients) == 2
    
    await hub.remove_client(mock_ws1)
    assert len(hub.clients) == 1
    assert mock_ws1 not in hub.clients
    assert mock_ws2 in hub.clients
    
    await hub.remove_client(mock_ws2)
    assert len(hub.clients) == 0


@pytest.mark.asyncio
async def test_room_hub_broadcast():
    """UC-06 : Test broadcast message à tous les clients."""
    hub = RoomHub("TEST123")
    
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    
    await hub.add_client(mock_ws1)
    await hub.add_client(mock_ws2)
    
    message = {"type": "game_event", "event": {"id": 1, "type": "bumper_hit"}}
    await hub.broadcast(message)
    
    mock_ws1.send_json.assert_called_once_with(message)
    mock_ws2.send_json.assert_called_once_with(message)
