from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.usecase.start_game_usecase import StartGameUseCase
from app.usecase.add_game_event_usecase import AddGameEventUseCase
from app.usecase.finish_game_usecase import FinishGameUseCase
from app.usecase.get_game_state_usecase import GetGameStateUseCase
from app.usecase.get_room_state_usecase import GetRoomStateUseCase
from app.infrastructure.db.player_repository import PlayerRepository
from app.infrastructure.db.room_repository import RoomRepository
from app.infrastructure.db.game_repository import GameRepository
from app.infrastructure.db.game_event_repository import GameEventRepository
from app.infrastructure import di  


# Schemas de requête et réponse pour l'endpoint /games/start
class StartGameRequest(BaseModel):
    pseudo: str
    mode: GameMode
    room_code: str | None = None


class StartGameResponse(BaseModel):
    player_id: int
    room_code: str
    game_id: int
    event_id: int


class AddGameEventRequest(BaseModel):
    type: GameEventType
    points: int = 0


class AddGameEventResponse(BaseModel):
    game_id: int
    new_score: int
    event_id: int


class FinishGameResponse(BaseModel):
    game_id: int
    status: str
    finished_at: datetime
    event_id: int


class GameEventDTO(BaseModel):
    id: int
    type: str
    points: int
    occured_at: datetime


class GetGameStateResponse(BaseModel):
    game_id: int
    player_id: int
    score: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    events: list[GameEventDTO]


class GameWithEventsDTO(BaseModel):
    game_id: int
    player_id: int
    score: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    events: list[GameEventDTO]


class GetRoomStateResponse(BaseModel):
    room_code: str
    mode: str
    status: str
    games: list[GameWithEventsDTO]


router = APIRouter(prefix="/games", tags=["games"])


@router.post("/start", status_code=status.HTTP_201_CREATED, response_model=StartGameResponse)
async def start_game(
    request: StartGameRequest,
    player_repo: PlayerRepository = Depends(di.get_player_repo),
    room_repo: RoomRepository = Depends(di.get_room_repo),
    game_repo: GameRepository = Depends(di.get_game_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo)
):
    """Démarre une nouvelle partie."""
    try: 
        usecase = StartGameUseCase(player_repo, room_repo, game_repo, event_repo)
        
        result = await usecase.execute(
            pseudo=request.pseudo,
            mode=request.mode,
            room_code=request.room_code
        )
        
        return StartGameResponse(
            player_id=result["player"].id,
            room_code=result["room"].code,
            game_id=result["game"].id,
            event_id=result["event"].id
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur lors du démarrage de la partie")


@router.post("/{game_id}/events", status_code=status.HTTP_201_CREATED, response_model=AddGameEventResponse)
async def add_game_event(
    game_id: int,
    request: AddGameEventRequest,
    game_repo: GameRepository = Depends(di.get_game_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo)
):
    """Ajoute un événement à une game en cours."""
    try:
        usecase = AddGameEventUseCase(game_repo, event_repo)
        
        result = await usecase.execute(
            game_id=game_id,
            event_type=request.type,
            points=request.points
        )
        
        return AddGameEventResponse(
            game_id=result["game"].id,
            new_score=result["game"].score,
            event_id=result["event"].id
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur lors de l'ajout de l'événement")


@router.post("/{game_id}/finish", status_code=status.HTTP_200_OK, response_model=FinishGameResponse)
async def finish_game(
    game_id: int,
    game_repo: GameRepository = Depends(di.get_game_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo)
):
    """Termine une game en cours."""
    try:
        usecase = FinishGameUseCase(game_repo, event_repo)
        
        result = await usecase.execute(game_id=game_id)
        
        return FinishGameResponse(
            game_id=result["game"].id,
            status=result["game"].status.value,
            finished_at=result["game"].finished_at,
            event_id=result["event"].id
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur lors de la fin de la partie")


@router.get("/{game_id}", status_code=status.HTTP_200_OK, response_model=GetGameStateResponse)
async def get_game_state(
    game_id: int,
    game_repo: GameRepository = Depends(di.get_game_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo)
):
    """Récupère l'état complet d'une game avec ses événements."""
    try:
        usecase = GetGameStateUseCase(game_repo, event_repo)
        
        result = await usecase.execute(game_id=game_id)
        
        events = [
            GameEventDTO(
                id=e.id,
                type=e.type.value,
                points=e.points,
                occured_at=e.occured_at
            )
            for e in result["events"]
        ]
        
        return GetGameStateResponse(
            game_id=result["game"].id,
            player_id=result["game"].player_id,
            score=result["game"].score,
            status=result["game"].status.value,
            started_at=result["game"].started_at,
            finished_at=result["game"].finished_at,
            events=events
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération de la partie")


@router.get("/rooms/{code}/state", status_code=status.HTTP_200_OK, response_model=GetRoomStateResponse)
async def get_room_state(
    code: str,
    room_repo: RoomRepository = Depends(di.get_room_repo),
    game_repo: GameRepository = Depends(di.get_game_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo)
):
    """Récupère l'état complet d'une room avec ses games et événements."""
    try:
        usecase = GetRoomStateUseCase(room_repo, game_repo, event_repo)
        
        result = await usecase.execute(room_code=code)
        
        games_dtos = []
        for item in result["games_with_events"]:
            game = item["game"]
            events = item["events"]
            
            events_dtos = [
                GameEventDTO(
                    id=e.id,
                    type=e.type.value,
                    points=e.points,
                    occured_at=e.occured_at
                )
                for e in events
            ]
            
            games_dtos.append(GameWithEventsDTO(
                game_id=game.id,
                player_id=game.player_id,
                score=game.score,
                status=game.status.value,
                started_at=game.started_at,
                finished_at=game.finished_at,
                events=events_dtos
            ))
        
        return GetRoomStateResponse(
            room_code=result["room"].code,
            mode=result["room"].mode.value,
            status=result["room"].status.value,
            games=games_dtos
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération de l'état de la room")