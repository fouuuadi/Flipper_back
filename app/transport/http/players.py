from fastapi import APIRouter, Depends, status, HTTPException

from app.domain.exceptions import PlayerNotFoundError
from app.domain.ports.player_repository import PlayerRepository
from app import di
from app.transport.http.schemas.players import (
    CreatePlayerRequest,
    CreatePlayerResponse,
    GetPlayerResponse,
    PlayerDTO,
)
from app.usecase.create_or_get_player_usecase import CreateOrGetPlayerUseCase
from app.usecase.get_player_usecase import GetPlayerUseCase

router = APIRouter(prefix="/players", tags=["players"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatePlayerResponse)
async def create_or_get_player(
    request: CreatePlayerRequest,
    player_repo: PlayerRepository = Depends(di.get_player_repo),
):
    """Crée ou récupère un joueur par pseudo.
    
    """
    try:
        usecase = CreateOrGetPlayerUseCase(player_repo)
        result = await usecase.execute(pseudo=request.pseudo)
        
        player = result["player"]
        created = result["created"]
        
        return CreatePlayerResponse(
            player=PlayerDTO(
                id=player.id,
                pseudo=player.pseudo,
                created_at=player.created_at,
            ),
            created=created,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{player_id}", response_model=GetPlayerResponse)
async def get_player(
    player_id: int,
    player_repo: PlayerRepository = Depends(di.get_player_repo),
):
    """Récupère un joueur par ID."""
    try:
        usecase = GetPlayerUseCase(player_repo)
        result = await usecase.execute(player_id=player_id)
        
        player = result["player"]
        
        return GetPlayerResponse(
            player=PlayerDTO(
                id=player.id,
                pseudo=player.pseudo,
                created_at=player.created_at,
            ),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except PlayerNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
