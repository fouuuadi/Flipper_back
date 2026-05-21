from app.infrastructure.db.room_repository import RoomRepository
from app.infrastructure.db.game_repository import GameRepository


class JoinRoomUseCase:
    """
    Valide que la room existe et retourne son état.
    Permet au client de se connecter à une room via son code.
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
            raise ValueError(f"Room {room_code} not found")
        
        # Récupérer les games actives 
        games = await self.game_repository.get_active_by_room(room.id)
        
        return {
            "room": room,
            "games": games if games else []
        }
