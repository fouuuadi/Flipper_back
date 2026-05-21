from datetime import datetime

from pydantic import BaseModel

from app.transport.http.schemas.game_state import GameEventDTO


class RoomGameDTO(BaseModel):
    game_id: int
    player_id: int
    score: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    events: list[GameEventDTO]


class RoomStateResponse(BaseModel):
    room_code: str
    mode: str
    status: str
    games: list[RoomGameDTO]
