from app.domain.exceptions import RoomNotFoundError
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.room_repository import RoomRepository


class JoinRoomUseCase:
    """Rejoint une room par son code : valide qu'elle existe et renvoie son état.

    On retourne aussi les parties actives dans la foulée pour éviter au client un
    second appel juste après avoir rejoint (flux REST legacy rooms/games).
    """

    def __init__(self, room_repository: RoomRepository, game_repository: GameRepository):
        self.room_repository = room_repository
        self.game_repository = game_repository

    async def execute(self, room_code: str) -> dict:
        """
        Valide et récupère une room par son code.
        """
        # Récupérer la room par son code
        room = await self.room_repository.get_by_code(room_code)
        
        if not room:
            raise RoomNotFoundError(f"Room {room_code} not found")
        
        # Récupérer les games actives 
        games = await self.game_repository.get_active_by_room(room.id)
        
        return {
            "room": room,
            "games": games if games else []
        }
