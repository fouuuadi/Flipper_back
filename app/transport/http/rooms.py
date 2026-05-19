from fastapi import APIRouter, HTTPException, status, Depends
from app.usecase.create_room_usecase import CreateRoomUseCase
from app.usecase.join_room_usecase import JoinRoomUseCase
from app.infrastructure.db.room_repository import RoomRepository
from app.infrastructure.db.game_repository import GameRepository
from app.infrastructure import di
from app.transport.http.dtos import (
    CreateRoomRequest,
    CreateRoomResponse,
    JoinRoomResponse,
    RoomGameDTO,
)


router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateRoomResponse)
async def create_room(
    request: CreateRoomRequest,
    room_repo: RoomRepository = Depends(di.get_room_repo),
):
    try:
        usecase = CreateRoomUseCase(room_repo)
        
        result = await usecase.execute(request.mode)
        room = result["room"]
        
        return CreateRoomResponse(
            room_code=room.code,
            mode=room.mode.value,
            status=room.status.value,
            created_at=room.created_at,
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur lors de la création de la room")


@router.post("/{code}/join", status_code=status.HTTP_200_OK, response_model=JoinRoomResponse)
async def join_room(
    code: str,
    room_repo: RoomRepository = Depends(di.get_room_repo),
    game_repo: GameRepository = Depends(di.get_game_repo),
):
    try:
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
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur lors de la jointure de la room")
