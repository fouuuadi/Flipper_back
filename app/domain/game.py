from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class GameMode(str, Enum):
    SOLO = "solo"
    ONE_V_ONE = "1v1"


class GameStatus(str, Enum):
    PLAYING = "playing"
    FINISHED = "finished"


class Game(BaseModel):
    id: int | None = None
    match_id: int | None = None
    player_id: int
    mode: GameMode
    score: int = 0
    status: GameStatus = GameStatus.PLAYING
    started_at: datetime = datetime.now()
    finished_at: datetime | None = None
