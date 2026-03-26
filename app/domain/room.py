from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from app.domain.game import GameMode


class RoomStatus(str, Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


class Room(BaseModel):
    id: int | None = None
    code: str
    mode: GameMode
    status: RoomStatus = RoomStatus.WAITING
    created_at: datetime = datetime.now()
