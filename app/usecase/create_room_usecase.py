from app.domain.game import GameMode
from app.domain.ports.room_repository import RoomRepository


class CreateRoomUseCase:
    """    
    Permet aux clients de créer une room sans démarrer de partie.
    """

    def __init__(self, room_repository: RoomRepository):
        self.room_repository = room_repository

    async def execute(self, mode: GameMode) -> dict:
        room = await self.room_repository.create(mode)
        return {"room": room}
