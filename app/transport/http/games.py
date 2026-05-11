from fastapi import APIRouter, HTTPException, status, Depends
from app.usecase.start_game_usecase import StartGameUseCase
from app.usecase.add_game_event_usecase import AddGameEventUseCase
from app.usecase.finish_game_usecase import FinishGameUseCase
from app.usecase.get_game_state_usecase import GetGameStateUseCase
from app.usecase.get_room_state_usecase import GetRoomStateUseCase
from app.infrastructure.db.player_repository import PlayerRepository
from app.infrastructure.db.room_repository import RoomRepository
from app.infrastructure.db.game_repository import GameRepository
from app.infrastructure.db.game_event_repository import GameEventRepository
from app.infrastructure.ws.room_hub import HubManager
from app.infrastructure import di
from app.transport.http.dtos import (
    StartGameRequest,
    StartGameResponse,
    AddGameEventRequest,
    AddGameEventResponse,
    FinishGameResponse,
    GameEventDTO,
    GetGameStateResponse,
    GameWithEventsDTO,
    GetRoomStateResponse,
)


router = APIRouter(prefix="/games", tags=["games"])


@router.post("/start", status_code=status.HTTP_201_CREATED, response_model=StartGameResponse)
async def start_game(
    request: StartGameRequest,
    player_repo: PlayerRepository = Depends(di.get_player_repo),
    room_repo: RoomRepository = Depends(di.get_room_repo),
    game_repo: GameRepository = Depends(di.get_game_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo),
    hub_manager: HubManager = Depends(di.get_hub_manager)
):
    """Démarre une nouvelle partie."""
    try: 
        usecase = StartGameUseCase(player_repo, room_repo, game_repo, event_repo)
        
        result = await usecase.execute(
            pseudo=request.pseudo,
            mode=request.mode,
            room_code=request.room_code
        )
        
        # Broadcaster le GAME_STARTED event aux clients WebSocket de la room
        message = {
            "type": "game_started",
            "event": {
                "id": result["event"].id,
                "game_id": result["game"].id,
                "type": result["event"].type.value,
                "points": result["event"].points,
                "occured_at": result["event"].occured_at.isoformat()
            }
        }
        await hub_manager.broadcast_to_room(result["room"].code, message)
        
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
    room_repo: RoomRepository = Depends(di.get_room_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo),
    hub_manager: HubManager = Depends(di.get_hub_manager)
):
    """Ajoute un événement à une game en cours et le broadcast aux clients WebSocket."""
    try:
        usecase = AddGameEventUseCase(game_repo, event_repo)
        
        result = await usecase.execute(
            game_id=game_id,
            event_type=request.type,
            points=request.points
        )
        
        # Récupérer la room pour connaître le room_code
        game = result["game"]
        room = await room_repo.get_by_id(game.room_id)
        
        # Construire le message à broadcaster
        message = {
            "type": "game_event",
            "event": {
                "id": result["event"].id,
                "game_id": result["event"].game_id,
                "type": result["event"].type.value,
                "points": result["event"].points,
                "occured_at": result["event"].occured_at.isoformat()
            }
        }
        
        # Broadcaster l'événement aux clients de la room
        await hub_manager.broadcast_to_room(room.code, message)
        
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
    room_repo: RoomRepository = Depends(di.get_room_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo),
    hub_manager: HubManager = Depends(di.get_hub_manager)
):
    """Termine une game en cours."""
    try:
        usecase = FinishGameUseCase(game_repo, event_repo)
        
        result = await usecase.execute(game_id=game_id)
        
        # Récupérer la room pour broadcaster le GAME_OVER event
        game = result["game"]
        room = await room_repo.get_by_id(game.room_id)
        
        # Broadcaster le GAME_OVER event aux clients WebSocket de la room
        message = {
            "type": "game_finished",
            "event": {
                "id": result["event"].id,
                "game_id": result["event"].game_id,
                "type": result["event"].type.value,
                "points": result["event"].points,
                "occured_at": result["event"].occured_at.isoformat()
            }
        }
        await hub_manager.broadcast_to_room(room.code, message)
        
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