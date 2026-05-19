from app.domain.exceptions import GameAlreadyFinishedError, GameNotFoundError
from app.domain.game import GameStatus
from app.domain.game_event import GameEventType
from app.infrastructure.db.game_repository import GameRepository
from app.infrastructure.db.game_event_repository import GameEventRepository


class FinishGameUseCase:
    """
    Usecase pour terminer une game en cours.
    """

    def __init__(
        self,
        game_repo: GameRepository,
        event_repo: GameEventRepository
    ):
        self.game_repo = game_repo
        self.event_repo = event_repo

    async def execute(self, game_id: int) -> dict:
        """
        Termine une game en cours.
            - Vérifie que la game existe
            - Vérifie que le status est PLAYING (sinon erreur)
            - Marque la game comme FINISHED avec finished_at=NOW()
            - Crée un événement GAME_OVER (points=0)
            - Retourne {game, event}
        """
        game = await self.game_repo.get_by_id(game_id)
        if not game:
            raise GameNotFoundError(f"Game avec ID '{game_id}' n'existe pas")

        if game.status != GameStatus.PLAYING:
            raise GameAlreadyFinishedError(f"Impossible de finir une game en état {game.status}")
        
        # Marquer la game comme FINISHED
        game = await self.game_repo.finish(game_id)
        
        # Créer un événement GAME_OVER
        event = await self.event_repo.create(game_id, GameEventType.GAME_OVER, 0)
        
        return {
            "game": game,
            "event": event
        }
