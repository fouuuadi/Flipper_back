"""
Gestionnaire des connexions WebSocket par room.
Permet aux clients de s'abonner à une room et aux messages d'être broadcastés.
"""
from typing import List, Dict
from fastapi import WebSocket


class RoomHub:
    """
    Gère les connexions WebSocket pour une room spécifique.
    """

    def __init__(self, room_code: str):
        """
        Initialise un hub pour une room.
        """
        self.room_code = room_code
        self.clients: List[WebSocket] = []

    async def add_client(self, websocket: WebSocket) -> None:
        """
        Ajoute un client WebSocket à la room.
        """
        self.clients.append(websocket)

    async def remove_client(self, websocket: WebSocket) -> None:
        """
        Retire un client WebSocket de la room.
        """
        if websocket in self.clients:
            self.clients.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        """
        Envoie un message à tous les clients connectés de la room.
        """
        # Un client peut s'être déconnecté entre-temps : on isole chaque envoi pour
        # qu'une socket morte ne bloque pas la diffusion aux autres. L'erreur est
        # ignorée volontairement, le client sera retiré à sa prochaine déconnexion.
        for client in self.clients:
            try:
                await client.send_json(message)
            except Exception:
                pass


class HubManager:
    """
    Gestionnaire global de tous les room hubs.
    """

    def __init__(self):
        self._rooms: Dict[str, RoomHub] = {}

    def get_or_create_room_hub(self, room_code: str) -> RoomHub:
        """
        Récupère ou crée un hub pour une room.
        """
        if room_code not in self._rooms:
            self._rooms[room_code] = RoomHub(room_code)
        return self._rooms[room_code]

    def get_room_hub(self, room_code: str) -> RoomHub | None:
        """
        Récupère un hub existant pour une room.
        Retourne None si la room n'a pas de hub.
        """
        return self._rooms.get(room_code)

    async def broadcast_to_room(self, room_code: str, message: dict) -> None:
        """
        Envoie un message à tous les clients d'une room.
        """
        hub = self.get_room_hub(room_code)
        if hub:
            await hub.broadcast(message)


hub_manager = HubManager()
