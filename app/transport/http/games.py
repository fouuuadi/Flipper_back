from fastapi import APIRouter, Depends, status

from app.domain.ports.game_event_repository import GameEventRepository
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.room_repository import RoomRepository
from app import di
from app.transport.http.schemas.add_event import AddEventRequest, AddEventResponse
from app.transport.http.schemas.finish_game import FinishGameResponse
from app.transport.http.schemas.game_state import GameEventDTO, GameStateResponse
from app.transport.http.schemas.list_rooms_games import ListGamesResponse, GameListItemDTO
from app.transport.http.schemas.room_state import RoomGameDTO, RoomStateResponse
from app.transport.http.schemas.start_game import StartGameRequest, StartGameResponse
from app.usecase.add_game_event_usecase import AddGameEventUseCase
from app.usecase.finish_game_usecase import FinishGameUseCase
from app.usecase.get_game_state_usecase import GetGameStateUseCase
from app.usecase.get_room_state_usecase import GetRoomStateUseCase
from app.usecase.start_game_usecase import StartGameUseCase
from app.usecase.list_rooms_games_usecase import ListGamesUseCase

router = APIRouter(prefix="/games", tags=["games"])


@router.post("/start", status_code=status.HTTP_201_CREATED, response_model=StartGameResponse)
async def start_game(request: StartGameRequest):
    """Démarre une nouvelle partie."""
    usecase = StartGameUseCase(di.get_uow)

    result = await usecase.execute(
        pseudo=request.pseudo,
        mode=request.mode,
        room_code=request.room_code,
    )

    return StartGameResponse(
        player_id=result["player"].id,
        room_code=result["room"].code,
        game_id=result["game"].id,
        event_id=result["event"].id,
    )


@router.post(
    "/{game_id}/events",
    status_code=status.HTTP_201_CREATED,
    response_model=AddEventResponse,
)
async def add_game_event(
    game_id: int,
    request: AddEventRequest,
    game_repo: GameRepository = Depends(di.get_game_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo),
):
    """Ajoute un événement à une game en cours."""
    usecase = AddGameEventUseCase(game_repo, event_repo)

    result = await usecase.execute(
        game_id=game_id,
        event_type=request.type,
        points=request.points,
    )

    return AddEventResponse(
        game_id=result["game"].id,
        new_score=result["game"].score,
        event_id=result["event"].id,
    )


@router.post(
    "/{game_id}/finish",
    status_code=status.HTTP_200_OK,
    response_model=FinishGameResponse,
)
async def finish_game(
    game_id: int,
    game_repo: GameRepository = Depends(di.get_game_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo),
):
    """Termine une game en cours."""
    usecase = FinishGameUseCase(game_repo, event_repo)

    result = await usecase.execute(game_id=game_id)

    return FinishGameResponse(
        game_id=result["game"].id,
        status=result["game"].status.value,
        finished_at=result["game"].finished_at,
        event_id=result["event"].id,
    )


@router.get(
    "/list",
    status_code=status.HTTP_200_OK,
    response_model=ListGamesResponse,
)
async def list_games(
    status: str | None = None,
    game_repo: GameRepository = Depends(di.get_game_repo),
):
    """Liste toutes les games filtrées par status."""
    usecase = ListGamesUseCase(game_repo)

    result = await usecase.execute(status=status)

    games_dtos = [
        GameListItemDTO(
            game_id=game.id,
            room_id=game.room_id,
            player_id=game.player_id,
            score=game.score,
            status=game.status.value,
            mode=game.mode.value,
            started_at=game.started_at,
        )
        for game in result["games"]
    ]

    return ListGamesResponse(games=games_dtos)


# NB : les routes statiques (/list, /rooms/{code}/state) doivent être déclarées
# AVANT la route paramétrée /{game_id}. Sinon FastAPI fait matcher "list" sur
# {game_id} et la route est inatteignable (422 à la conversion en int).
@router.get(
    "/{game_id}",
    status_code=status.HTTP_200_OK,
    response_model=GameStateResponse,
)
async def get_game_state(
    game_id: int,
    game_repo: GameRepository = Depends(di.get_game_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo),
):
    """Récupère l'état complet d'une game avec ses événements."""
    usecase = GetGameStateUseCase(game_repo, event_repo)

    result = await usecase.execute(game_id=game_id)

    events = [
        GameEventDTO(
            id=e.id,
            type=e.type.value,
            points=e.points,
            occured_at=e.occured_at,
        )
        for e in result["events"]
    ]

    return GameStateResponse(
        game_id=result["game"].id,
        player_id=result["game"].player_id,
        score=result["game"].score,
        status=result["game"].status.value,
        started_at=result["game"].started_at,
        finished_at=result["game"].finished_at,
        events=events,
    )


@router.get(
    "/rooms/{code}/state",
    status_code=status.HTTP_200_OK,
    response_model=RoomStateResponse,
)
async def get_room_state(
    code: str,
    room_repo: RoomRepository = Depends(di.get_room_repo),
    game_repo: GameRepository = Depends(di.get_game_repo),
    event_repo: GameEventRepository = Depends(di.get_event_repo),
):
    """Récupère l'état complet d'une room avec ses games et événements."""
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
                occured_at=e.occured_at,
            )
            for e in events
        ]

        games_dtos.append(RoomGameDTO(
            game_id=game.id,
            player_id=game.player_id,
            score=game.score,
            status=game.status.value,
            started_at=game.started_at,
            finished_at=game.finished_at,
            events=events_dtos,
        ))

    return RoomStateResponse(
        room_code=result["room"].code,
        mode=result["room"].mode.value,
        status=result["room"].status.value,
        games=games_dtos,
    )