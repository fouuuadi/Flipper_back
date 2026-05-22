from app.domain.game import GameStatus
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.room_repository import RoomRepository
from app.domain.room import RoomStatus


class ListRoomsUseCase:
    def __init__(self, room_repo: RoomRepository):
        self.room_repo = room_repo

    async def execute(self, status: str | None = None) -> dict:
        """
        Liste les rooms filtrées par status.
        """
        if status:
            room_status = RoomStatus(status.lower())
            rooms = await self.room_repo.get_by_status(room_status)
        else:
            # Si pas de filtre, on retourne toutes les rooms
            # (Optionnel : vous pouvez implémenter get_all() ou faire la requête ici)
            rooms = []
            for status_value in RoomStatus:
                rooms.extend(await self.room_repo.get_by_status(status_value))

        return {"rooms": rooms}


class ListGamesUseCase:
    def __init__(self, game_repo: GameRepository):
        self.game_repo = game_repo

    async def execute(self, status: str | None = None) -> dict:
        """
        Liste les games filtrées par status.
        """
        if status:
            game_status = GameStatus(status.lower())
            games = await self.game_repo.get_by_status(game_status)
        else:
            # Si pas de filtre, on retourne toutes les games
            games = []
            for status_value in GameStatus:
                games.extend(await self.game_repo.get_by_status(status_value))

        return {"games": games}
