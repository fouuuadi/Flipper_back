from fastapi import APIRouter, Depends, Query, status

from app import di
from app.domain.ports.player_repository import PlayerRepository
from app.transport.http.schemas.players import CreatePlayerRequest, PlayerResponse
from app.usecase.create_or_get_player_usecase import CreateOrGetPlayerUseCase
from app.usecase.get_player_usecase import GetPlayerUseCase

router = APIRouter(prefix="/players", tags=["players"])


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    response_model=PlayerResponse,
)
async def create_or_get_player(
    request: CreatePlayerRequest,
    player_repo: PlayerRepository = Depends(di.get_player_repo),
):
    usecase = CreateOrGetPlayerUseCase(player_repo)
    player = await usecase.execute(request.pseudo)
    return PlayerResponse(
        id=player.id,
        pseudo=player.pseudo,
        created_at=player.created_at,
    )


@router.get(
    "/{player_id}",
    status_code=status.HTTP_200_OK,
    response_model=PlayerResponse,
)
async def get_player_by_id(
    player_id: int,
    player_repo: PlayerRepository = Depends(di.get_player_repo),
):
    usecase = GetPlayerUseCase(player_repo)
    player = await usecase.execute_by_id(player_id)
    return PlayerResponse(
        id=player.id,
        pseudo=player.pseudo,
        created_at=player.created_at,
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=PlayerResponse,
)
async def get_player_by_pseudo(
    pseudo: str = Query(..., description="Pseudo to look up (raw or formatted)"),
    player_repo: PlayerRepository = Depends(di.get_player_repo),
):
    usecase = GetPlayerUseCase(player_repo)
    player = await usecase.execute_by_pseudo(pseudo)
    return PlayerResponse(
        id=player.id,
        pseudo=player.pseudo,
        created_at=player.created_at,
    )
