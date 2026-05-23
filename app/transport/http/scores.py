from fastapi import APIRouter, Depends, status

from app import di
from app.domain.ports.event_buffer import EventBuffer
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.session_store import SessionStore
from app.transport.http.schemas.scores import (
    FinishSessionRequest,
    FinishSessionResponse,
)
from app.usecase.finish_and_persist_usecase import FinishAndPersistUseCase

router = APIRouter(prefix="/scores", tags=["scores"])


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    response_model=FinishSessionResponse,
    response_model_by_alias=True,
)
async def finish_session(
    request: FinishSessionRequest,
    session_store: SessionStore = Depends(di.get_session_store),
    event_buffer: EventBuffer = Depends(di.get_event_buffer),
    game_repository: GameRepository = Depends(di.get_game_repo),
):
    usecase = FinishAndPersistUseCase(
        session_store=session_store,
        event_buffer=event_buffer,
        game_repository=game_repository,
    )
    result = await usecase.execute(request.session_id)
    return FinishSessionResponse(
        final_score=result.final_score,
        player_id=result.player_id,
        game_id=result.game_id,
        event_count=result.event_count,
    )
