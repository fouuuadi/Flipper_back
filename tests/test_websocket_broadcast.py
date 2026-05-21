import pytest
from unittest.mock import AsyncMock
from app.infrastructure.ws.room_hub import HubManager


@pytest.mark.asyncio
async def test_broadcast_to_room_with_connected_clients():
    """UC-07 : Test broadcast d'un événement à plusieurs clients connectés."""
    hub_manager = HubManager()
    
    # Créer un hub pour la room ABC
    hub = hub_manager.get_or_create_room_hub("ABC123")
    
    # Ajouter 2 clients connectés
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    await hub.add_client(mock_ws1)
    await hub.add_client(mock_ws2)
    
    assert len(hub.clients) == 2
    
    # Broadcaster un événement
    message = {
        "type": "game_event",
        "event": {
            "id": 1,
            "game_id": 100,
            "type": "bumper_hit",
            "points": 100,
            "occured_at": "2026-05-11T10:30:45"
        }
    }
    await hub_manager.broadcast_to_room("ABC123", message)
    
    # Vérifier que les 2 clients ont reçu le message
    mock_ws1.send_json.assert_called_once_with(message)
    mock_ws2.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_broadcast_to_room_with_no_clients():
    """UC-07 : Test broadcast quand aucun client n'est connecté (graceful)."""
    hub_manager = HubManager()
    
    # Broadcaster à une room sans clients connectés
    message = {
        "type": "game_event",
        "event": {
            "id": 1,
            "game_id": 100,
            "type": "bumper_hit",
            "points": 100,
            "occured_at": "2026-05-11T10:30:45"
        }
    }
    
    # Pas d'erreur si pas de clients
    await hub_manager.broadcast_to_room("NONEXISTENT", message)
    
    # Vérifier que le hub n'existe pas
    hub = hub_manager.get_room_hub("NONEXISTENT")
    assert hub is None


@pytest.mark.asyncio
async def test_broadcast_game_over_event():
    """UC-07 : Test broadcast d'un événement GAME_OVER."""
    hub_manager = HubManager()
    
    # Créer hub et ajouter client
    hub = hub_manager.get_or_create_room_hub("ROOM001")
    mock_ws = AsyncMock()
    await hub.add_client(mock_ws)
    
    # Broadcaster GAME_OVER
    message = {
        "type": "game_finished",
        "event": {
            "id": 5,
            "game_id": 200,
            "type": "game_over",
            "points": 0,
            "occured_at": "2026-05-11T10:45:00"
        }
    }
    await hub_manager.broadcast_to_room("ROOM001", message)
    
    # Vérifier que le client a reçu l'événement GAME_OVER
    mock_ws.send_json.assert_called_once_with(message)
    
    # Le type doit être "game_finished"
    called_message = mock_ws.send_json.call_args[0][0]
    assert called_message["type"] == "game_finished"
    assert called_message["event"]["type"] == "game_over"


@pytest.mark.asyncio
async def test_broadcast_game_started_event():
    """UC-07 : Test broadcast d'un événement GAME_STARTED."""
    hub_manager = HubManager()
    
    # Créer hub et ajouter 2 clients
    hub = hub_manager.get_or_create_room_hub("GAME123")
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    await hub.add_client(mock_ws1)
    await hub.add_client(mock_ws2)
    
    # Broadcaster GAME_STARTED
    message = {
        "type": "game_started",
        "event": {
            "id": 1,
            "game_id": 300,
            "type": "game_started",
            "points": 0,
            "occured_at": "2026-05-11T10:00:00"
        }
    }
    await hub_manager.broadcast_to_room("GAME123", message)
    
    # Vérifier que les 2 clients ont reçu
    mock_ws1.send_json.assert_called_once_with(message)
    mock_ws2.send_json.assert_called_once_with(message)
    
    # Vérifier le type
    called_message = mock_ws1.send_json.call_args[0][0]
    assert called_message["type"] == "game_started"
