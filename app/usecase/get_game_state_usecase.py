from app.domain.exceptions import GameNotFoundError
from app.domain.ports.game_event_repository import GameEventRepository
from app.domain.ports.game_repository import GameRepository


class GetGameStateUseCase:
    """
    Usecase pour récupérer l'état complet d'une game
    """

    def __init__(
        self,
        game_repo: GameRepository,
        event_repo: GameEventRepository
    ):
        self.game_repo = game_repo
        self.event_repo = event_repo

    async def execute(self, game_id: int, events_limit: int = 10) -> dict:
        """
        Récupère une game et ses événements récents.
            - Vérifie que la game existe
            - Récupère la game
            - Récupère les N derniers events (ORDER BY occured_at DESC)
            - Retourne {game, events}
        """
        game = await self.game_repo.get_by_id(game_id)
        if not game:
            raise GameNotFoundError(f"Game avec ID '{game_id}' n'existe pas")
        
        events = await self.event_repo.get_by_game_id(game_id, limit=events_limit)
        
        return {
            "game": game,
            "events": events
        }
