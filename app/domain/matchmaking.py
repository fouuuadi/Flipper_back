from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class MatchmakingStatus(str, Enum):
    """Statuts possibles pour le matchmaking"""
    WAITING = "waiting"     
    MATCHED = "matched"   
    CANCELLED = "cancelled" 


class Matchmaking(BaseModel):
    id: int | None = None
    player1_id: int
    player2_id: int | None = None
    status: MatchmakingStatus
    mode: str  # "1v1"
    created_at: datetime = datetime.now()
