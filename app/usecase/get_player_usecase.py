from app.domain.ports.player_repository import PlayerRepository
from app.domain.exceptions import PlayerNotFoundError


class GetPlayerUseCase:
    """
    Permet aux clients de récupérer un joueur par ID.
    """

    def __init__(self, player_repository: PlayerRepository):
        self.player_repository = player_repository

    async def execute(self, player_id: int) -> dict:
        # Valider l'ID
        if not player_id or player_id <= 0:
            raise ValueError("Player ID doit être un entier positif")
        
        player = await self.player_repository.get_by_id(player_id)
        if not player:
            raise PlayerNotFoundError(f"Joueur avec l'ID {player_id} introuvable")
        
        return {"player": player}
