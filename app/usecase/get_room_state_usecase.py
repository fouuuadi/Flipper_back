from app.domain.exceptions import RoomNotFoundError
from app.infrastructure.db.room_repository import RoomRepository
from app.infrastructure.db.game_repository import GameRepository
from app.infrastructure.db.game_event_repository import GameEventRepository


class GetRoomStateUseCase:
    """
    Usecase pour récupérer l'état complet d'une room
    """

    def __init__(
        self,
        room_repo: RoomRepository,
        game_repo: GameRepository,
        event_repo: GameEventRepository
    ):
        self.room_repo = room_repo
        self.game_repo = game_repo
        self.event_repo = event_repo

    async def execute(self, room_code: str, events_limit: int = 10) -> dict:
        """
        Récupère une room et ses games actives avec leurs événements.
            - Vérifie que la room existe
            - Récupère la room par code
            - Récupère les games PLAYING de cette room
            - Pour chaque game : récupère les N derniers events
            - Retourne {room, games_with_events}
        """
        room = await self.room_repo.get_by_code(room_code)
        if not room:
            raise RoomNotFoundError(f"Room avec code '{room_code}' n'existe pas")
        
        games = await self.game_repo.get_active_by_room(room.id)
        
        # Enrichir chaque game avec ses events
        games_with_events = []
        for game in games:
            events = await self.event_repo.get_by_game_id(game.id, limit=events_limit)
            games_with_events.append({
                "game": game,
                "events": events
            })
        
        return {
            "room": room,
            "games_with_events": games_with_events
        }
