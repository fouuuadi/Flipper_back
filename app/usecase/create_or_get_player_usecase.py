from app.domain.exceptions import PlayerAlreadyExistsError
from app.domain.ports.player_repository import PlayerRepository


class CreateOrGetPlayerUseCase:
    """
    Permet aux clients de créer ou récupérer un joueur par pseudo.
    Si le pseudo existe → retourne le joueur existant
    Si le pseudo n'existe pas → crée le joueur et le retourne
    """

    def __init__(self, player_repository: PlayerRepository):
        self.player_repository = player_repository

    async def execute(self, pseudo: str) -> dict:
        # Valider le pseudo
        if not pseudo or not pseudo.strip():
            raise ValueError("Pseudo ne peut pas être vide")
        
        pseudo = pseudo.strip()
        
        existing_player = await self.player_repository.get_by_pseudo(pseudo)
        if existing_player:
            return {
                "player": existing_player,
                "created": False
            }
        
        try:
            new_player = await self.player_repository.create(pseudo)
            return {
                "player": new_player,
                "created": True
            }
        except PlayerAlreadyExistsError:
            player = await self.player_repository.get_by_pseudo(pseudo)
            return {
                "player": player,
                "created": False
            }
