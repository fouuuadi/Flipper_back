from fastapi import APIRouter, Depends, Query, status

from app import di
from app.domain.game import GameMode
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.player_repository import PlayerRepository
from app.transport.http.schemas.players import (
    CreatePlayerRequest,
    PlayerHistoryGameDTO,
    PlayerHistoryResponse,
    PlayerResponse,
)
from app.usecase.create_or_get_player_usecase import CreateOrGetPlayerUseCase
from app.usecase.get_player_history_usecase import GetPlayerHistoryUseCase
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


@router.get(
    "/{player_id}/games",
    status_code=status.HTTP_200_OK,
    response_model=PlayerHistoryResponse,
)
async def get_player_history(
    player_id: int,
    mode: GameMode | None = Query(default=None, description="Filter by game mode"),
    limit: int = Query(default=20, ge=1, le=100, description="Max games to return (1..100)"),
    player_repo: PlayerRepository = Depends(di.get_player_repo),
    game_repo: GameRepository = Depends(di.get_game_repo),
):
    usecase = GetPlayerHistoryUseCase(player_repo, game_repo)
    player, games = await usecase.execute(player_id=player_id, mode=mode, limit=limit)
    return PlayerHistoryResponse(
        player_id=player.id,
        pseudo=player.pseudo,
        games=[
            PlayerHistoryGameDTO(
                game_id=g.id,
                mode=g.mode.value,
                score=g.score,
                started_at=g.started_at,
                finished_at=g.finished_at,
            )
            for g in games
        ],
    )
