from datetime import datetime
from pydantic import BaseModel, Field


class PlayerDTO(BaseModel):
    id: int
    pseudo: str
    created_at: datetime


class CreatePlayerRequest(BaseModel):
    """Requête pour créer ou récupérer un joueur."""
    pseudo: str = Field(..., min_length=1, max_length=50)


class CreatePlayerResponse(BaseModel):
    """Réponse pour création/récupération d'un joueur."""
    player: PlayerDTO
    created: bool


class GetPlayerResponse(BaseModel):
    """Réponse pour récupération d'un joueur par ID."""
    player: PlayerDTO
