from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from app.domain.game import GameMode
from app.domain.game_event import GameEventType
from app.usecase.start_game_usecase import StartGameUseCase
from app.usecase.add_game_event_usecase import AddGameEventUseCase
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