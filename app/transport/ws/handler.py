import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from app.infrastructure import di
from app.infrastructure.ws.room_hub import hub_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_subscribe(
    websocket: WebSocket,
    room_repository=Depends(di.get_room_repo)
):
    """
    UC-06 : S'abonner à une room via WebSocket.
    
    Paramètres :
    - room_code (query param) : Code de la room à laquelle s'abonner
    
    Comportement :
    1. Valide que room_code est fourni
    2. Valide que la room existe en DB
    3. Ajoute le client au hub de la room
    4. Maintient la connexion ouverte
    5. À la déconnexion, retire le client du hub
    """
    room_code = websocket.query_params.get("room_code")
    
    if not room_code:
        await websocket.close(code=1000, reason="room_code required")
        return
    
    room = await room_repository.get_by_code(room_code)
    if not room:
        await websocket.close(code=1000, reason="room not found")
        return
    
    await websocket.accept()
    logger.info("[ws] connected to room %s", room_code)
    
    hub = hub_manager.get_or_create_room_hub(room_code)
    await hub.add_client(websocket)
    
    try:
        while True:
            await websocket.receive_text()
            # UC-07 implémentera le broadcast des events
    except WebSocketDisconnect:
        await hub.remove_client(websocket)
        logger.info("[ws] disconnected from room %s", room_code)
