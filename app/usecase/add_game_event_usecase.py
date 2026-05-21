from app.domain.exceptions import GameNotFoundError, GameNotPlayableError
from app.domain.game import GameStatus
from app.domain.game_event import GameEventType
from app.infrastructure.db.game_repository import GameRepository
from app.infrastructure.db.game_event_repository import GameEventRepository


class AddGameEventUseCase:
    """
    Usecase pour ajouter un événement à une game en cours.
    """

    def __init__(
        self,
        game_repo: GameRepository,
        event_repo: GameEventRepository
    ):
        self.game_repo = game_repo
        self.event_repo = event_repo

    async def execute(
        self,
        game_id: int,
        event_type: GameEventType,
        points: int = 0
    ) -> dict:
        """
        Ajoute un événement à une game et met à jour le score.
            - Vérifie que la game existe et est en état PLAYING
            - Crée l'event
            - Si points > 0, ajoute les points à la game
            - Retourne {game, event}
        """
        game = await self.game_repo.get_by_id(game_id)
        if not game:
            raise GameNotFoundError(f"Game avec ID '{game_id}' n'existe pas")

        if game.status != GameStatus.PLAYING:
            raise GameNotPlayableError(f"Impossible d'ajouter un événement à une game en état {game.status}")
        
        event = await self.event_repo.create(game_id, event_type, points)
        
        if points > 0:
            game = await self.game_repo.add_points(game_id, points)
        
        return {
            "game": game,
            "event": event
        }
