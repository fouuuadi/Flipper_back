from app.domain.exceptions import RoomNotFoundError
from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.infrastructure.db.player_repository import PlayerRepository
from app.infrastructure.db.room_repository import RoomRepository
from app.infrastructure.db.game_repository import GameRepository
from app.infrastructure.db.game_event_repository import GameEventRepository


class StartGameUseCase:
    """
    Usecase pour démarrer une partie.
    """

    def __init__(
        self,
        player_repo: PlayerRepository,
        room_repo: RoomRepository,
        game_repo: GameRepository,
        event_repo: GameEventRepository
    ):
        self.player_repo = player_repo
        self.room_repo = room_repo
        self.game_repo = game_repo
        self.event_repo = event_repo

    async def execute(
        self, 
        pseudo: str, 
        mode: GameMode,
        room_code: str | None = None
    ) -> dict:
        """
        Exécute le flux de démarrage de partie.
        """
        player = await self.player_repo.get_by_pseudo(pseudo)
        if not player:
            player = await self.player_repo.create(pseudo)
        
        if room_code:
            room = await self.room_repo.get_by_code(room_code)
            if not room:
                raise RoomNotFoundError(f"Room avec code '{room_code}' n'existe pas")
        else:
            room = await self.room_repo.create(mode)
        
        game = await self.game_repo.create(player.id, room.id, mode)
        
        event = await self.event_repo.create(game.id, GameEventType.GAME_STARTED)
        
        return {
            "player": player,
            "room": room,
            "game": game,
            "event": event
        }