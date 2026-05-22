from datetime import datetime
from pydantic import BaseModel



class RoomListItemDTO(BaseModel):
    room_code: str
    mode: str
    status: str
    created_at: datetime


class GameListItemDTO(BaseModel):
    game_id: int
    room_id: int | None
    player_id: int
    score: int
    status: str
    mode: str
    started_at: datetime


class ListRoomsResponse(BaseModel):
    rooms: list[RoomListItemDTO]


class ListGamesResponse(BaseModel):
    games: list[GameListItemDTO]
