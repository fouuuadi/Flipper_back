from datetime import datetime

from pydantic import BaseModel


class GameEventDTO(BaseModel):
    id: int
    type: str
    points: int
    occured_at: datetime


class GameStateResponse(BaseModel):
    game_id: int
    player_id: int
    score: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    events: list[GameEventDTO]
