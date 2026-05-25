from fastapi import APIRouter, Depends, status

from app import di
from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster
from app.domain.ports.session_store import SessionStore
from app.transport.http.schemas.sessions import (
    CreateSessionRequest,
    CreateSessionResponse,
    ReadyUpResponse,
)
from app.usecase.create_session_usecase import CreateSessionUseCase
from app.usecase.ready_up_usecase import ReadyUpUseCase
from app.usecase.start_countdown_usecase import StartCountdownUseCase

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateSessionResponse,
)
async def create_session(
    request: CreateSessionRequest,
    session_store: SessionStore = Depends(di.get_session_store),
):
    usecase = CreateSessionUseCase(session_store)
    session = await usecase.execute(
        pseudo=request.pseudo,
        mode=request.mode,
        room_code=request.room_code,
    )
    return CreateSessionResponse(
        session_id=session.session_id,
        pseudo=session.pseudo,
        status=session.status.value,
        mode=session.mode.value,
        room_code=session.room_code,
    )


@router.post(
    "/{session_id}/ready",
    status_code=status.HTTP_200_OK,
    response_model=ReadyUpResponse,
)
async def ready_up(
    session_id: str,
    session_store: SessionStore = Depends(di.get_session_store),
    broadcaster: SessionEventBroadcaster = Depends(di.get_session_hub_manager),
):
    countdown = StartCountdownUseCase(session_store, broadcaster)
    usecase = ReadyUpUseCase(
        session_store=session_store,
        broadcaster=broadcaster,
        on_ready=countdown.execute,
    )
    session = await usecase.execute(session_id)
    return ReadyUpResponse(
        session_id=session.session_id,
        status=session.status.value,
    )
