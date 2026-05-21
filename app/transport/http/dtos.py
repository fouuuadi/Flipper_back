"""
DTOs pour la couche Transport HTTP
Séparation des responsabilités : DTOs dans ce fichier, routes dans games.py
"""

from datetime import datetime
from pydantic import BaseModel
from app.domain.game import GameMode
from app.domain.game_event import GameEventType


# UC-01 : Démarrer une partie

class StartGameRequest(BaseModel):
    pseudo: str
    mode: GameMode
    room_code: str | None = None


class StartGameResponse(BaseModel):
    player_id: int
    room_code: str
    game_id: int
    event_id: int


# UC-02 : Ajouter un événement

class AddGameEventRequest(BaseModel):
    type: GameEventType
    points: int = 0


class AddGameEventResponse(BaseModel):
    game_id: int
    new_score: int
    event_id: int


# UC-03 : Terminer une partie

class FinishGameResponse(BaseModel):
    game_id: int
    status: str
    finished_at: datetime
    event_id: int


# UC-04 : Récupérer l'état

class GameEventDTO(BaseModel):
    """DTO pour un événement de jeu (utilisé dans les réponses GET)"""
    id: int
    type: str
    points: int
    occured_at: datetime


# UC-04 : Récupérer l'état d'une partie (GET /games/{game_id})
class GetGameStateResponse(BaseModel):
    game_id: int
    player_id: int
    score: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    events: list[GameEventDTO]


# UC-04 : Récupérer l'état d'une room (GET /rooms/{code}/state)
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


# UC-07 : Broadcast WebSocket (DTOs pour les messages temps réel)

class GameEventBroadcastEvent(BaseModel):
    """Structure de l'événement dans les messages WebSocket"""
    id: int
    game_id: int
    type: str
    points: int
    occured_at: str 


class GameEventBroadcastDTO(BaseModel):
    """Message broadcast pour les événements de gameplay (BUMPER_HIT, BALL_LOST, etc.)"""
    type: str = "game_event"
    event: GameEventBroadcastEvent


class GameStartedBroadcastDTO(BaseModel):
    """Message broadcast pour le démarrage d'une partie"""
    type: str = "game_started"
    event: GameEventBroadcastEvent


class GameFinishedBroadcastDTO(BaseModel):
    """Message broadcast pour la fin d'une partie"""
    type: str = "game_finished"
    event: GameEventBroadcastEvent


# UC-08 : Créer une room

class CreateRoomRequest(BaseModel):
    mode: GameMode


class CreateRoomResponse(BaseModel):
    room_code: str
    mode: str
    status: str
    created_at: datetime


# UC-09 : Rejoindre une room

class RoomGameDTO(BaseModel):
    game_id: int
    player_id: int
    score: int
    status: str


class JoinRoomResponse(BaseModel):
    room_code: str
    mode: str
    status: str
    games: list[RoomGameDTO] = []