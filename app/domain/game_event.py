from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class GameEventType(str, Enum):
    GAME_STARTED = "game_started"
    BUMPER_HIT = "bumper_hit"
    BALL_LOST = "ball_lost"
    BONUS = "bonus"
    FLIPPER_HIT = "flipper_hit"
    GAME_OVER = "game_over"


class GameEvent(BaseModel):
    id: int | None = None
    game_id: int
    type: GameEventType
    points: int = 0
    occured_at: datetime = datetime.now()
