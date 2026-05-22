from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class SessionStatus(str, Enum):
    WAITING = "waiting"   # session créée, en attente du ready
    READY = "ready"       # joueur prêt, en attente du game:start
    PLAYING = "playing"   # partie en cours
    OVER = "over"         # partie finie, en attente du POST /scores


DEFAULT_LIVES = 3


class Session(BaseModel):
    session_id: str
    pseudo: str
    score: int = 0
    lives: int = DEFAULT_LIVES
    combo: int = 0
    status: SessionStatus = SessionStatus.WAITING
    room_code: str | None = None
    created_at: datetime
