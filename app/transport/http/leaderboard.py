from fastapi import APIRouter, Depends, Query, status

from app import di
from app.domain.game import GameMode
from app.domain.ports.game_repository import GameRepository
from app.transport.http.schemas.leaderboard import (
    LeaderboardEntryDTO,
    LeaderboardResponse,
)
from app.usecase.get_leaderboard_usecase import GetLeaderboardUseCase

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=LeaderboardResponse,
)
async def get_leaderboard(
    mode: GameMode | None = Query(default=None, description="Filter by game mode"),
    limit: int = Query(default=10, ge=1, le=100, description="Top N (1..100)"),
    game_repo: GameRepository = Depends(di.get_game_repo),
):
    usecase = GetLeaderboardUseCase(game_repo)
    entries = await usecase.execute(mode=mode, limit=limit)
    return LeaderboardResponse(
        mode=mode.value if mode is not None else None,
        limit=limit,
        entries=[
            LeaderboardEntryDTO(
                rank=e.rank,
                player_id=e.player_id,
                pseudo=e.pseudo,
                score=e.score,
            )
            for e in entries
        ],
    )
