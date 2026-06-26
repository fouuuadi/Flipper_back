from fastapi import APIRouter, Depends, status

from app import di
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.matchmaking_repository import MatchmakingRepository
from app.domain.ports.player_repository import PlayerRepository
from app.domain.ports.room_repository import RoomRepository
from app.domain.ports.session_service import SessionService
from app.transport.http.schemas.matchmaking import (
    MatchmakingRequest,
    MatchmakingResponse,
)
from app.usecase.matchmaking_usecase import MatchmakingUseCase

router = APIRouter(prefix="/matchmaking", tags=["matchmaking"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=MatchmakingResponse,
)
async def matchmaking(
    request: MatchmakingRequest,
    matchmaking_repo: MatchmakingRepository = Depends(di.get_matchmaking_repo),
    room_repo: RoomRepository = Depends(di.get_room_repo),
    game_repo: GameRepository = Depends(di.get_game_repo),
    player_repo: PlayerRepository = Depends(di.get_player_repo),
    session_service: SessionService = Depends(di.get_session_service),
):
    usecase = MatchmakingUseCase(
        matchmaking_repo=matchmaking_repo,
        room_repo=room_repo,
        game_repo=game_repo,
        player_repo=player_repo,
        session_service=session_service,
    )

    result = await usecase.execute(
        player_id=request.player_id,
        mode=request.mode,
    )

    return MatchmakingResponse(**result)