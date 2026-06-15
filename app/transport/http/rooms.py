from fastapi import APIRouter, status, Depends
from app.usecase.create_room_usecase import CreateRoomUseCase
from app.usecase.join_room_usecase import JoinRoomUseCase
from app.usecase.list_rooms_games_usecase import ListRoomsUseCase
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.room_repository import RoomRepository
from app import di
from app.transport.http.dtos import (
    CreateRoomRequest,
    CreateRoomResponse,
    JoinRoomResponse,
    RoomGameDTO,
)
from app.transport.http.schemas.list_rooms_games import ListRoomsResponse, RoomListItemDTO


router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateRoomResponse)
async def create_room(
    request: CreateRoomRequest,
    room_repo: RoomRepository = Depends(di.get_room_repo),
):
    usecase = CreateRoomUseCase(room_repo)
    result = await usecase.execute(request.mode)
    room = result["room"]

    return CreateRoomResponse(
        room_code=room.code,
        mode=room.mode.value,
        status=room.status.value,
        created_at=room.created_at,
    )


@router.post("/{code}/join", status_code=status.HTTP_200_OK, response_model=JoinRoomResponse)
async def join_room(
    code: str,
    room_repo: RoomRepository = Depends(di.get_room_repo),
    game_repo: GameRepository = Depends(di.get_game_repo),
):
    usecase = JoinRoomUseCase(room_repo, game_repo)
    result = await usecase.execute(code)
    room = result["room"]
    games = result["games"]

    games_dtos = [
        RoomGameDTO(
            game_id=game.id,
            player_id=game.player_id,
            score=game.score,
            status=game.status.value,
        )
        for game in games
    ]

    return JoinRoomResponse(
        room_code=room.code,
        mode=room.mode.value,
        status=room.status.value,
        games=games_dtos,
    )


@router.get(
    "/list",
    status_code=status.HTTP_200_OK,
    response_model=ListRoomsResponse,
)
async def list_rooms(
    status: str | None = None,
    room_repo: RoomRepository = Depends(di.get_room_repo),
):
    """Liste toutes les rooms filtrées par status."""
    usecase = ListRoomsUseCase(room_repo)

    result = await usecase.execute(status=status)

    rooms_dtos = [
        RoomListItemDTO(
            room_code=room.code,
            mode=room.mode.value,
            status=room.status.value,
            created_at=room.created_at,
        )
        for room in result["rooms"]
    ]

    return ListRoomsResponse(rooms=rooms_dtos)
